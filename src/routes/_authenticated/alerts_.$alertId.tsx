import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Panel, RiskBadge, StatusBadge } from "@/components/sentinel";
import { alertQuery, eventsByIdsQuery } from "@/lib/queries";
import { suggestedAction } from "@/lib/scoring";
import { supabase } from "@/integrations/supabase/client";
import { useState } from "react";
import { useServerFn } from "@tanstack/react-start";
import { summarizeAlert } from "@/lib/summary.functions";

export const Route = createFileRoute("/_authenticated/alerts_/$alertId")({
  head: () => ({
    meta: [
      { title: "Alert detail — SentinelAI" },
      { name: "description", content: "Why this activity was flagged: risk score, reasons and evidence." },
      { property: "og:title", content: "Alert detail — SentinelAI" },
      { property: "og:description", content: "Explainable insider-threat alert." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: AlertDetail,
});

function AlertDetail() {
  const { alertId } = Route.useParams();
  const qc = useQueryClient();
  const { data: a, isLoading, error } = useQuery(alertQuery(alertId));
  const ids = [...new Set((a?.reasons ?? []).flatMap((r) => r.event_ids))];
  const events = useQuery({ ...eventsByIdsQuery(ids), enabled: !!a });

  async function setStatus(status: string) {
    const { error } = await supabase.from("risk_scores").update({ status }).eq("id", alertId);
    if (error) { toast.error(error.message); return; }
    toast.success(`Alert marked ${status}`);
    qc.invalidateQueries();
  }

  const summarize = useServerFn(summarizeAlert);
  const [summary, setSummary] = useState<string | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  async function runSummary() {
    setAiBusy(true);
    try { setSummary((await summarize({ data: { id: alertId } })).summary); }
    catch (e) { toast.error(e instanceof Error ? e.message : "Summary failed"); }
    finally { setAiBusy(false); }
  }

  if (isLoading) return <p className="text-muted-foreground">Loading…</p>;
  if (error || !a) return <p className="text-destructive">Alert not found.</p>;
  const emp = a.employees;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link to="/alerts" className="font-mono text-xs uppercase tracking-[0.25em] text-muted-foreground hover:text-primary">← Alerts</Link>
          <h1 className="mt-1 text-2xl font-semibold">
            <Link to="/users/$employeeId" params={{ employeeId: a.employee_id }} className="hover:text-primary">{emp.full_name as string}</Link>
            <span className="ml-3 font-mono text-base text-muted-foreground">{a.date}</span>
          </h1>
          <p className="text-sm text-muted-foreground">{emp.role as string} · {emp.department as string} · {a.employee_id}</p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={a.status} />
          <Button variant="secondary" size="sm" onClick={() => setStatus("reviewed")}>Mark reviewed</Button>
          <Button size="sm" onClick={() => setStatus("escalated")}>Escalate</Button>
          <Button variant="ghost" size="sm" onClick={() => setStatus("dismissed")}>Dismiss</Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Risk score">
          <div className="flex items-end gap-3">
            <span className="font-mono text-6xl">{a.risk_score}</span>
            <span className="pb-2 font-mono text-muted-foreground">/100</span>
          </div>
          <RiskBadge level={a.risk_level} className="mt-3" />
          <p className="mt-4 font-mono text-xs text-muted-foreground">Isolation Forest anomaly score: {a.anomaly_score.toFixed(3)}</p>
          <div className="mt-4 rounded-sm border border-border bg-secondary p-3 text-sm">
            <p className="font-mono text-xs uppercase tracking-wider text-primary">Suggested action</p>
            <p className="mt-1">{suggestedAction(a.risk_level)}</p>
          </div>
        </Panel>

        <Panel title="Why it was flagged" className="lg:col-span-2">
          {a.reasons.length === 0 ? (
            <p className="text-sm text-muted-foreground">No specific rule fired; the model found this day's combination of activity statistically unusual for this user.</p>
          ) : (
            <ul className="space-y-2">
              {a.reasons.map((r) => (
                <li key={r.code} className="flex items-start justify-between gap-4 rounded-sm border border-border p-3">
                  <div>
                    <p className="font-medium">{r.text}</p>
                    <p className="font-mono text-xs text-muted-foreground">{r.code} · {r.event_ids.length} related events</p>
                  </div>
                  <span className="font-mono text-sm text-primary">+{r.severity}</span>
                </li>
              ))}
            </ul>
          )}
          <details className="mt-4">
            <summary className="cursor-pointer font-mono text-xs uppercase tracking-wider text-muted-foreground">Feature vector</summary>
            <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-xs sm:grid-cols-3">
              {Object.entries(a.features).map(([k, v]) => <div key={k} className="flex justify-between"><span className="text-muted-foreground">{k}</span><span>{Number(v).toFixed(Number.isInteger(v) ? 0 : 1)}</span></div>)}
            </div>
          </details>
        </Panel>
      </div>

      <Panel title="AI analyst summary">
        {summary ? <p className="whitespace-pre-wrap text-sm leading-relaxed">{summary}</p> : <p className="text-sm text-muted-foreground">Generate a plain-English briefing of this alert and recommended next steps.</p>}
        <Button size="sm" variant="secondary" className="mt-3" disabled={aiBusy} onClick={runSummary}>{aiBusy ? "Writing…" : summary ? "Regenerate" : "Generate summary"}</Button>
      </Panel>

      <Panel title={`Related raw events (${events.data?.length ?? 0})`}>
        <div className="max-h-96 overflow-auto">
          <table className="w-full font-mono text-xs">
            <thead className="sticky top-0 bg-card text-left text-muted-foreground"><tr><th className="py-1.5">Time (UTC)</th><th>Activity</th><th>Device</th><th>IP</th><th>Location</th><th>Detail</th></tr></thead>
            <tbody className="divide-y divide-border">
              {(events.data ?? []).map((e) => (
                <tr key={e.id}><td className="py-1.5">{e.ts.slice(0, 19).replace("T", " ")}</td><td>{e.activity}</td><td>{e.device}</td><td>{e.ip}</td><td>{e.location}</td><td className="text-muted-foreground">{String((e.metadata as Record<string, unknown>)?.["file"] ?? (e.metadata as Record<string, unknown>)?.["serial"] ?? "")}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
