import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Panel, RiskBadge } from "@/components/sentinel";
import { employeeDetailQuery } from "@/lib/queries";
import { HIGH_THRESHOLD, MEDIUM_THRESHOLD } from "@/lib/scoring";

export const Route = createFileRoute("/_authenticated/users/$employeeId")({
  head: () => ({
    meta: [
      { title: "User profile — SentinelAI" },
      { name: "description", content: "Behavioral baseline, risk history and recent activity for one employee." },
      { property: "og:title", content: "User profile — SentinelAI" },
      { property: "og:description", content: "Risk history and recent activity for one employee." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: UserDetail,
});

function UserDetail() {
  const { employeeId } = Route.useParams();
  const { data, isLoading, error } = useQuery(employeeDetailQuery(employeeId));
  if (isLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (error || !data) return <p className="text-destructive">User not found.</p>;
  const { employee: e, scores, events, devices } = data;
  const anomalies = scores.filter((s) => s.risk_level !== "Low").reverse();

  return (
    <div className="space-y-6">
      <div>
        <Link to="/dashboard" className="font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground hover:text-primary">← Dashboard</Link>
        <h1 className="mt-1 text-2xl font-semibold">{e.full_name}</h1>
        <p className="text-sm text-muted-foreground">{e.role} · {e.department} · {e.id}</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Baseline behavior">
          <dl className="space-y-2 text-sm">
            {[
              ["Normal hours", `${e.normal_login_start}:00 – ${e.normal_login_end}:00`],
              ["Avg daily downloads", e.normal_download_count],
              ["Home location", e.home_location],
              ["Primary device", e.primary_device],
            ].map(([k, v]) => <div key={k as string} className="flex justify-between"><dt className="text-muted-foreground">{k}</dt><dd className="font-mono">{v}</dd></div>)}
          </dl>
          <p className="mt-4 font-mono text-xs uppercase tracking-wider text-muted-foreground">Devices seen</p>
          <div className="mt-2 flex flex-wrap gap-1.5">{devices.map((d) => <span key={d} className={`rounded-sm border px-2 py-0.5 font-mono text-xs ${d === e.primary_device ? "border-border" : "border-risk-high/50 text-risk-high"}`}>{d}</span>)}</div>
        </Panel>
        <Panel title="Risk history" className="lg:col-span-2">
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={scores.map((s) => ({ date: s.date.slice(5), risk: s.risk_score }))}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="date" stroke="var(--muted-foreground)" fontSize={11} />
                <YAxis domain={[0, 100]} stroke="var(--muted-foreground)" fontSize={11} />
                <Tooltip contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", fontSize: 12 }} />
                <ReferenceLine y={HIGH_THRESHOLD} stroke="var(--risk-high)" strokeDasharray="4 4" />
                <ReferenceLine y={MEDIUM_THRESHOLD} stroke="var(--risk-medium)" strokeDasharray="4 4" />
                <Line dataKey="risk" stroke="var(--primary)" strokeWidth={2} dot={{ r: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Recent anomalies">
          <ul className="divide-y divide-border">
            {anomalies.map((s) => (
              <li key={s.id}>
                <Link to="/alerts/$alertId" params={{ alertId: s.id }} className="flex items-center justify-between gap-3 py-2.5 hover:text-primary">
                  <div><p className="font-mono text-sm">{s.date}</p><p className="text-xs text-muted-foreground">{s.reasons[0]?.text ?? "Statistical outlier"}</p></div>
                  <RiskBadge level={s.risk_level} />
                </Link>
              </li>
            ))}
            {anomalies.length === 0 && <li className="py-2 text-sm text-muted-foreground">No anomalies on record.</li>}
          </ul>
        </Panel>
        <Panel title="Recent activity">
          <div className="max-h-80 overflow-auto font-mono text-xs">
            {events.map((ev) => (
              <div key={ev.id} className="flex gap-3 border-b border-border py-1.5">
                <span className="text-muted-foreground">{ev.ts.slice(5, 16).replace("T", " ")}</span>
                <span className="w-28">{ev.activity}</span><span className="text-muted-foreground">{ev.location} · {ev.ip}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
