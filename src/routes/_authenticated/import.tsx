import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/sentinel";
import { get, post } from "@/lib/api";

export const Route = createFileRoute("/_authenticated/import")({
  head: () => ({
    meta: [
      { title: "Import CERT data · SentinelAI" },
      { name: "description", content: "Upload CERT insider-threat CSV files and score them." },
      { property: "og:title", content: "Import CERT data · SentinelAI" },
      { property: "og:description", content: "Upload CERT insider-threat CSV files and score them." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: ImportPage,
});

type IngestReport = { rows_read: number; inserted: number; skipped_by_reason: Record<string, number> };
type Job = { status: "running" | "done" | "error"; report: { error?: string; users?: IngestReport; events?: IngestReport; scored?: number } | null };

async function waitForJob(id: string): Promise<Job> {
  let job: Job;
  do {
    await new Promise((resolve) => setTimeout(resolve, 1500));
    job = await get<Job>(`/jobs/${encodeURIComponent(id)}`);
  } while (job.status === "running");
  if (job.status === "error") throw new Error(job.report?.error || "Job failed");
  return job;
}

function ImportPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const qc = useQueryClient();
  const say = (s: string) => setLog((l) => [...l, s]);

  async function go() {
    setBusy(true); setLog([]);
    try {
      const body = new FormData();
      files.forEach((file) => body.append("files", file));
      say("Uploading CSV files…");
      const upload = await post<{ job_id: string }>("/ingest/run", body);
      const ingested = await waitForJob(upload.job_id);
      const report = ingested.report;
      for (const [name, result] of [["Users", report?.users], ["Events", report?.events]] as const) {
        if (!result) continue;
        const skipped = Object.entries(result.skipped_by_reason).map(([reason, count]) => `${reason}: ${count}`).join(", ");
        say(`${name}: ${result.rows_read} rows read, ${result.inserted} inserted, ${skipped || "0 skipped"}`);
      }
      say("Running detection…");
      const scoring = await post<{ job_id: string }>("/score/run");
      const completed = await waitForJob(scoring.job_id);
      say(`Done: ${completed.report?.scored ?? 0} user-days scored`);
      await qc.invalidateQueries();
      toast.success("CERT data imported and scored");
    } catch (e) {
      const message = e instanceof Error ? e.message : "Import failed";
      say(`Error: ${message}`);
      toast.error(message);
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-xl font-bold tracking-wide">Import CERT dataset</h1>
      <Panel title="Upload CSV files">
        <p className="mb-4 text-sm text-muted-foreground">
          Choose <span className="font-mono">logon.csv</span>, <span className="font-mono">device.csv</span> and/or <span className="font-mono">file.csv</span> from the CERT insider-threat dataset.
          Logons become logins, USB connects become USB events, and file copies become downloads; then every user-day is scored.
        </p>
        <input type="file" accept=".csv" multiple onChange={(e) => setFiles([...(e.target.files ?? [])])}
          className="block text-sm file:mr-3 file:rounded-sm file:border-0 file:bg-accent file:px-3 file:py-1.5 file:text-foreground" />
        <Button className="mt-4" disabled={!files.length || busy} onClick={go}>
          <Upload className="size-4" />{busy ? "Importing…" : "Import and score"}
        </Button>
        {log.length > 0 && <pre className="mt-4 whitespace-pre-wrap rounded-sm bg-muted p-3 font-mono text-xs">{log.join("\n")}</pre>}
      </Panel>
    </div>
  );
}
