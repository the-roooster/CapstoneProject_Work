import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { useServerFn } from "@tanstack/react-start";
import { useState } from "react";
import { toast } from "sonner";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Panel } from "@/components/sentinel";
import { supabase } from "@/integrations/supabase/client";
import { parseCert, MAX_ROWS_PER_FILE, type ParsedEvent } from "@/lib/cert-import";
import { runScoring } from "@/lib/scoring.functions";

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

function ImportPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const score = useServerFn(runScoring);
  const qc = useQueryClient();
  const say = (s: string) => setLog((l) => [...l, s]);

  async function go() {
    setBusy(true); setLog([]);
    try {
      const all: ParsedEvent[] = [];
      for (const f of files) {
        const r = parseCert(await f.text());
        say(`${f.name}: ${r.kind} file, ${r.events.length} events read, ${r.skipped} rows skipped`);
        all.push(...r.events);
      }
      if (!all.length) throw new Error("No usable rows found");
      const byUser = new Map<string, Map<string, number>>();
      for (const e of all) {
        const m = byUser.get(e.employee_id) ?? new Map<string, number>();
        m.set(e.device, (m.get(e.device) ?? 0) + 1);
        byUser.set(e.employee_id, m);
      }
      const { data: existing } = await supabase.from("employees").select("id");
      const known = new Set((existing ?? []).map((e) => e.id));
      const newEmps = [...byUser].filter(([id]) => !known.has(id)).map(([id, m]) => ({
        id, full_name: id, department: "CERT import", role: "Employee", home_location: "Unknown",
        primary_device: [...m].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "unknown",
      }));
      for (let i = 0; i < newEmps.length; i += 500) {
        const { error } = await supabase.from("employees").insert(newEmps.slice(i, i + 500));
        if (error) throw new Error(error.message);
      }
      say(`${newEmps.length} new employees added`);
      for (let i = 0; i < all.length; i += 1000) {
        const { error } = await supabase.from("events").insert(all.slice(i, i + 1000));
        if (error) throw new Error(error.message);
        if (i % 10000 === 0) say(`Saved ${Math.min(i + 1000, all.length)} / ${all.length} events…`);
      }
      say("Running detection…");
      const r = await score();
      say(`Done: ${r.scored} user-days scored, ${r.high} high and ${r.medium} medium risk`);
      await qc.invalidateQueries();
      toast.success("CERT data imported and scored");
    } catch (e) {
      say(`Error: ${(e as Error).message}`);
      toast.error((e as Error).message);
    } finally { setBusy(false); }
  }

  return (
    <div className="space-y-6">
      <h1 className="font-mono text-xl font-bold tracking-wide">Import CERT dataset</h1>
      <Panel title="Upload CSV files">
        <p className="mb-4 text-sm text-muted-foreground">
          Choose <span className="font-mono">logon.csv</span>, <span className="font-mono">device.csv</span> and/or <span className="font-mono">file.csv</span> from the CERT insider-threat dataset.
          Up to {MAX_ROWS_PER_FILE.toLocaleString()} rows are read from each file. Logons become logins, USB connects become USB events, and file copies become downloads; then every user-day is scored.
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
