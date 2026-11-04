import { createFileRoute, ClientOnly } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { Panel } from "@/components/sentinel";
import { supabase } from "@/integrations/supabase/client";
import type { LocationStat } from "@/lib/locations";

const LoginMap = lazy(() => import("@/components/LoginMap"));

export const Route = createFileRoute("/_authenticated/map")({
  head: () => ({
    meta: [
      { title: "Login map — SentinelAI" },
      { name: "description", content: "Where employees sign in from, with logins outside their home city highlighted." },
      { property: "og:title", content: "Login map — SentinelAI" },
      { property: "og:description", content: "Geographic view of employee logins." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: MapPage,
});

function MapPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["login-map"],
    queryFn: async () => {
      const [ev, emp] = await Promise.all([
        supabase.from("events").select("employee_id, location").eq("activity", "login").limit(10000),
        supabase.from("employees").select("id, full_name, home_location"),
      ]);
      if (ev.error) throw new Error(ev.error.message);
      const home = new Map((emp.data ?? []).map((e) => [e.id, e]));
      const m = new Map<string, LocationStat & { set: Set<string> }>();
      for (const e of ev.data ?? []) {
        const s = m.get(e.location) ?? { location: e.location, logins: 0, unusual: 0, users: [], set: new Set<string>() };
        s.logins++;
        const h = home.get(e.employee_id);
        if (h && h.home_location !== e.location) s.unusual++;
        s.set.add(h?.full_name ?? e.employee_id);
        m.set(e.location, s);
      }
      return [...m.values()].map(({ set, ...s }) => ({ ...s, users: [...set] })).sort((a, b) => b.logins - a.logins);
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Login map</h1>
        <p className="text-sm text-muted-foreground">Green: normal logins. Red: at least one login from outside the employee's home city.</p>
      </div>
      <Panel title="Login locations">
        {isLoading ? <p className="text-muted-foreground">Loading…</p> : error ? <p className="text-destructive">Could not load logins.</p> : (
          <ClientOnly fallback={<div className="h-[480px]" />}>
            <Suspense fallback={<div className="h-[480px]" />}><LoginMap stats={data ?? []} /></Suspense>
          </ClientOnly>
        )}
      </Panel>
      <Panel title="By city">
        <table className="w-full font-mono text-xs">
          <thead className="text-left text-muted-foreground"><tr><th className="py-1.5">City</th><th>Logins</th><th>Outside home city</th><th>Employees</th></tr></thead>
          <tbody className="divide-y divide-border">
            {(data ?? []).map((s) => (
              <tr key={s.location} className={s.unusual ? "text-destructive" : ""}><td className="py-1.5">{s.location}</td><td>{s.logins}</td><td>{s.unusual}</td><td>{s.users.length}</td></tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
