import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Panel, RiskBadge, StatusBadge } from "@/components/sentinel";
import { get } from "@/lib/api";

export const Route = createFileRoute("/_authenticated/alerts")({
  head: () => ({
    meta: [
      { title: "Alerts — SentinelAI" },
      { name: "description", content: "Filterable list of insider-threat alerts with their top reason." },
      { property: "og:title", content: "Alerts — SentinelAI" },
      { property: "og:description", content: "Filterable list of insider-threat alerts." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Alerts,
});

type AlertRow = {
  score_id: string; user_id: string; full_name: string; department: string;
  risk_score: number; risk_level: string; top_reason: string | null; date: string; investigation_status: string;
};
type User = { department: string };

const sel = "h-9 rounded-sm border border-input bg-background px-2 text-sm";

function Alerts() {
  const navigate = useNavigate();
  const [level, setLevel] = useState("all");
  const [dept, setDept] = useState("all");
  const [status, setStatus] = useState("all");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [sort, setSort] = useState<"risk" | "date">("risk");

  const filters = { level, department: dept, status, from, to, sort };
  const alerts = useQuery({
    queryKey: ["alerts", filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (level !== "all") params.set("level", level);
      if (dept !== "all") params.set("department", dept);
      if (status !== "all") params.set("status", status);
      if (from) params.set("from", from);
      if (to) params.set("to", to);
      params.set("sort", sort);
      params.set("limit", "1000");
      const all: AlertRow[] = [];
      for (let offset = 0; ; offset += 1000) {
        params.set("offset", String(offset));
        const page = await get<AlertRow[]>(`/alerts?${params.toString()}`);
        all.push(...page);
        if (page.length < 1000) return all;
      }
    },
  });
  const users = useQuery({ queryKey: ["users", "departments"], queryFn: () => get<User[]>("/users") });
  const depts = [...new Set((users.data ?? []).map((user) => user.department).filter(Boolean))].sort();
  const rows = alerts.data ?? [];
  const error = alerts.error ?? users.error;
  const filtered = level !== "all" || dept !== "all" || status !== "all" || !!from || !!to;

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground">Triage</p>
        <h1 className="text-2xl font-semibold">Alerts</h1>
      </div>
      {error && <div role="alert" className="rounded-md border border-destructive bg-card p-4 text-sm text-destructive">{error instanceof Error ? error.message : "Unable to load alerts."}</div>}
      {(alerts.isLoading || users.isLoading) && <p className="text-sm text-muted-foreground">Loading alerts…</p>}
      <Panel>
        <div className="flex flex-wrap items-center gap-3">
          <select className={sel} value={level} onChange={(e) => setLevel(e.target.value)} aria-label="Risk level">
            <option value="all">All levels</option><option>High</option><option>Medium</option>
          </select>
          <select className={sel} value={dept} onChange={(e) => setDept(e.target.value)} aria-label="Department">
            <option value="all">All departments</option>{depts.map((d) => <option key={d}>{d}</option>)}
          </select>
          <select className={sel} value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
            <option value="all">Any status</option><option value="open">Open</option><option value="reviewed">Reviewed</option><option value="escalated">Escalated</option><option value="dismissed">Dismissed</option>
          </select>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">From <input type="date" className={sel} value={from} onChange={(e) => setFrom(e.target.value)} /></label>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">To <input type="date" className={sel} value={to} onChange={(e) => setTo(e.target.value)} /></label>
          <select className={sel} value={sort} onChange={(e) => setSort(e.target.value as "risk" | "date")} aria-label="Sort">
            <option value="risk">Sort: risk</option><option value="date">Sort: newest</option>
          </select>
          <span className="ml-auto font-mono text-xs text-muted-foreground">{rows.length} alerts</span>
        </div>
      </Panel>
      <div className="overflow-x-auto rounded-md border border-border bg-card">
        <table className="w-full text-sm">
          <thead className="border-b border-border text-left font-mono text-xs uppercase tracking-wider text-muted-foreground">
            <tr><th className="px-4 py-2.5">User</th><th className="px-4">Risk</th><th className="px-4">Top reason</th><th className="px-4">Date</th><th className="px-4">Status</th></tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((r) => (
              <tr key={r.score_id} className="cursor-pointer hover:bg-accent" onClick={() => navigate({ to: "/alerts/$alertId", params: { alertId: r.score_id } })}>
                <td className="px-4 py-3">
                  <Link to="/alerts/$alertId" params={{ alertId: r.score_id }} className="font-medium hover:text-primary">{r.full_name}</Link>
                  <p className="font-mono text-xs text-muted-foreground">{r.user_id} · {r.department}</p>
                </td>
                <td className="px-4"><div className="flex items-center gap-2"><span className="w-8 font-mono">{r.risk_score}</span><RiskBadge level={r.risk_level} /></div></td>
                <td className="px-4 text-muted-foreground">{r.top_reason ?? "Statistical outlier"}</td>
                <td className="px-4 font-mono text-xs">{r.date}</td>
                <td className="px-4"><StatusBadge status={r.investigation_status} /></td>
              </tr>
            ))}
            {!alerts.isLoading && !alerts.isError && rows.length === 0 && <tr><td colSpan={5} className="px-4 py-8 text-center text-muted-foreground">{filtered ? "No alerts match these filters." : "No alerts yet. Run detection."}</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
