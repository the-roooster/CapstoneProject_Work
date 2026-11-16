import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel, RiskBadge, riskColor } from "@/components/sentinel";
import { get, post } from "@/lib/api";

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

type DashboardSummary = {
  open_counts: Record<string, number>;
  distribution: Record<string, number>;
  top_users: Array<{ user_id: string; full_name: string; department: string; risk_score: number; risk_level: string }>;
  total_user_days: number;
};
type TrendRow = { date: string; files: number; logins: number; failed: number; usb: number };
type Job = { status: "running" | "done" | "error"; report: { error?: string; scored?: number } | null };

const tooltipStyle = { background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 4, fontSize: 12 };

function Dashboard() {
  const qc = useQueryClient();
  const summary = useQuery({ queryKey: ["alerts", "summary"], queryFn: () => get<DashboardSummary>("/alerts/summary") });
  const trend = useQuery({ queryKey: ["events", "trend"], queryFn: () => get<TrendRow[]>("/events/trend") });
  const [running, setRunning] = useState(false);

  async function onRun() {
    setRunning(true);
    const toastId = toast.loading("Running detection…");
    try {
      const { job_id } = await post<{ job_id: string }>("/score/run");
      let job: Job;
      do {
        await new Promise((resolve) => setTimeout(resolve, 1500));
        job = await get<Job>(`/jobs/${encodeURIComponent(job_id)}`);
      } while (job.status === "running");
      if (job.status === "error") throw new Error(job.report?.error || "Scoring failed");
      await qc.invalidateQueries();
      toast.success("Detection complete", { id: toastId });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Scoring failed", { id: toastId });
    } finally {
      setRunning(false);
    }
  }

  const counts = summary.data?.open_counts;
  const dist = ["Low", "Medium", "High"].map((level) => ({ level, count: summary.data?.distribution[level] ?? 0 }));
  const topUsers = summary.data?.top_users ?? [];
  const error = summary.error ?? trend.error;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground">Overview</p>
          <h1 className="text-2xl font-semibold">Threat dashboard</h1>
        </div>
        <Button onClick={onRun} disabled={running}><Play className="size-4" />{running ? "Running detection…" : "Run detection"}</Button>
      </div>

      {error && <div role="alert" className="rounded-md border border-destructive bg-card p-4 text-sm text-destructive">{error instanceof Error ? error.message : "Unable to load dashboard."}</div>}
      {(summary.isLoading || trend.isLoading) && <p className="text-sm text-muted-foreground">Loading dashboard…</p>}
      {!summary.isLoading && !summary.isError && summary.data?.total_user_days === 0 && (
        <Panel><p className="text-sm text-muted-foreground">No alerts yet. Run detection.</p></Panel>
      )}

      <div className="grid gap-4 sm:grid-cols-4">
        <Stat label="Open alerts" value={(counts?.High ?? 0) + (counts?.Medium ?? 0)} />
        <Stat label="High" value={counts?.High ?? 0} tone="text-risk-high" />
        <Stat label="Medium" value={counts?.Medium ?? 0} tone="text-risk-medium" />
        <Stat label="User-days scored" value={summary.data?.total_user_days ?? 0} />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Top risky users" className="lg:col-span-1" action={<Link to="/alerts" className="text-xs text-primary hover:underline">View all alerts →</Link>}>
          <ul className="divide-y divide-border">
            {topUsers.map((r) => (
              <li key={r.user_id}>
                <Link to="/users/$employeeId" params={{ employeeId: r.user_id }} className="flex items-center justify-between gap-3 py-2.5 hover:text-primary">
                  <div>
                    <p className="text-sm font-medium">{r.full_name}</p>
                    <p className="font-mono text-xs text-muted-foreground">{r.user_id} · {r.department}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-lg">{r.risk_score}</span>
                    <RiskBadge level={r.risk_level} />
                  </div>
                </Link>
              </li>
            ))}
            {!summary.isLoading && !summary.isError && topUsers.length === 0 && <li className="py-2 text-sm text-muted-foreground">No alerts yet. Run detection.</li>}
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
