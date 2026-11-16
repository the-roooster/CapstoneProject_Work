import { createFileRoute, ClientOnly } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import { Panel } from "@/components/sentinel";
import { get } from "@/lib/api";
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
    queryFn: async () => (await get<LocationStat[]>("/events/locations")).sort((a, b) => b.logins - a.logins),
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
              <tr key={s.location} className={s.unusual ? "text-destructive" : ""}><td className="py-1.5">{s.location}</td><td>{s.logins}</td><td>{s.unusual}</td><td>{s.users.length === 10 ? "10+" : s.users.length}</td></tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
