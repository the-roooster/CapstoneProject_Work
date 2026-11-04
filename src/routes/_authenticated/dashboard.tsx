import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { useState } from "react";
import { toast } from "sonner";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, RiskBadge, riskColor } from "@/components/sentinel";
import { scoresQuery, eventTrendQuery } from "@/lib/queries";
import { runScoring } from "@/lib/scoring.functions";

export const Route = createFileRoute("/_authenticated/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard — SentinelAI" },
      { name: "description", content: "Active insider-threat alerts, risk distribution and top risky users." },
      { property: "og:title", content: "Dashboard — SentinelAI" },
      { property: "og:description", content: "Active insider-threat alerts at a glance." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Dashboard,
});

const tooltipStyle = { background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 4, fontSize: 12 };

function Dashboard() {
  const qc = useQueryClient();
  const scores = useQuery(scoresQuery);
  const trend = useQuery(eventTrendQuery);
  const run = useServerFn(runScoring);
  const [running, setRunning] = useState(false);

  async function onRun() {
    setRunning(true);
    try {
      const r = await run();
      toast.success(`Scored ${r.scored} user-days from ${r.events} events — ${r.high} high, ${r.medium} medium`);
      qc.invalidateQueries();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Scoring failed");
    } finally {
      setRunning(false);
    }
  }

  const rows = scores.data ?? [];
  const open = rows.filter((r) => r.risk_level !== "Low" && r.status === "open");
  const count = (l: string) => open.filter((r) => r.risk_level === l).length;
  const dist = ["Low", "Medium", "High"].map((l) => ({ level: l, count: rows.filter((r) => r.risk_level === l).length }));
  const topUsers = [...new Map(rows.map((r) => [r.employee_id, r])).values()]
    .sort((a, b) => b.risk_score - a.risk_score).slice(0, 6);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground">Overview</p>
          <h1 className="text-2xl font-semibold">Threat dashboard</h1>
        </div>
        <Button onClick={onRun} disabled={running}><Play className="size-4" />{running ? "Running detection…" : "Run detection"}</Button>
      </div>

      {!scores.isLoading && rows.length === 0 && (
        <Panel>
          <p className="text-sm text-muted-foreground">No risk scores yet. Click <span className="text-foreground">Run detection</span> to build features, train the Isolation Forest and score every user-day.</p>
        </Panel>
      )}

      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Open alerts" value={open.length} />
        <Stat label="High" value={count("High")} tone="text-risk-high" />
        <Stat label="Medium" value={count("Medium")} tone="text-risk-medium" />
        <Stat label="User-days scored" value={rows.length} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Top risky users" className="lg:col-span-1" action={<Link to="/alerts" className="text-xs text-primary hover:underline">View all alerts →</Link>}>
          <ul className="divide-y divide-border">
            {topUsers.map((r) => (
              <li key={r.employee_id}>
                <Link to="/users/$employeeId" params={{ employeeId: r.employee_id }} className="flex items-center justify-between gap-3 py-2.5 hover:text-primary">
                  <div>
                    <p className="text-sm font-medium">{r.employees?.full_name}</p>
                    <p className="font-mono text-xs text-muted-foreground">{r.employee_id} · {r.employees?.department}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-lg">{r.risk_score}</span>
                    <RiskBadge level={r.risk_level} />
                  </div>
                </Link>
              </li>
            ))}
            {topUsers.length === 0 && <li className="py-2 text-sm text-muted-foreground">Nothing yet.</li>}
          </ul>
        </Panel>

        <Panel title="Risk distribution (user-days)">
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={dist}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="level" stroke="var(--muted-foreground)" fontSize={12} />
                <YAxis stroke="var(--muted-foreground)" fontSize={12} scale="sqrt" />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "var(--accent)" }} />
                <Bar dataKey="count">{dist.map((d) => <Cell key={d.level} fill={riskColor(d.level)} />)}</Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Event trend">
          <div className="h-64">
            <ResponsiveContainer>
              <LineChart data={trend.data ?? []}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="date" stroke="var(--muted-foreground)" fontSize={11} />
                <YAxis stroke="var(--muted-foreground)" fontSize={11} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line dataKey="files" stroke="var(--chart-1)" dot={false} strokeWidth={2} />
                <Line dataKey="logins" stroke="var(--chart-2)" dot={false} strokeWidth={2} />
                <Line dataKey="failed" stroke="var(--chart-3)" dot={false} strokeWidth={2} />
                <Line dataKey="usb" stroke="var(--chart-4)" dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-md border border-border bg-card p-4">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className={`mt-2 font-mono text-3xl ${tone ?? ""}`}>{value}</p>
    </div>
  );
}
