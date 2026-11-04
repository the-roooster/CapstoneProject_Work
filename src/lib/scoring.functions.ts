import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";
import { scoreAll, type RawEvent, type Employee } from "./scoring";

/** Feature engineering + Isolation Forest + rule engine over all events; upserts RiskScores. */
export const runScoring = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .handler(async ({ context }) => {
    const sb = context.supabase;
    const { data: emps, error: e1 } = await sb.from("employees").select("*");
    if (e1) throw new Error(e1.message);

    const events: RawEvent[] = [];
    for (let from = 0; ; from += 1000) {
      const { data, error } = await sb.from("events")
        .select("id, employee_id, ts, activity, device, ip, location")
        .order("id").range(from, from + 999);
      if (error) throw new Error(error.message);
      events.push(...(data as RawEvent[]));
      if (!data || data.length < 1000) break;
    }

    const scores = scoreAll(emps as Employee[], events);
    for (let i = 0; i < scores.length; i += 200) {
      const chunk = scores.slice(i, i + 200).map((s) => ({ ...s, reasons: s.reasons as never, features: s.features as never, scored_at: new Date().toISOString() }));
      const { error } = await sb.from("risk_scores").upsert(chunk, { onConflict: "employee_id,date", ignoreDuplicates: false });
      if (error) throw new Error(error.message);
    }
    return {
      events: events.length,
      scored: scores.length,
      high: scores.filter((s) => s.risk_level === "High").length,
      medium: scores.filter((s) => s.risk_level === "Medium").length,
    };
  });
