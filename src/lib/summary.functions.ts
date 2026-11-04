import { createServerFn } from "@tanstack/react-start";
import { requireSupabaseAuth } from "@/integrations/supabase/auth-middleware";

/** AI-written analyst summary for one alert, via Lovable AI Gateway. */
export const summarizeAlert = createServerFn({ method: "POST" })
  .middleware([requireSupabaseAuth])
  .inputValidator((d: { id: string }) => {
    if (typeof d?.id !== "string" || d.id.length > 64) throw new Error("Invalid id");
    return d;
  })
  .handler(async ({ data, context }) => {
    const { data: a, error } = await context.supabase
      .from("risk_scores").select("*, employees(full_name, role, department, normal_login_start, normal_login_end, normal_download_count, home_location)")
      .eq("id", data.id).single();
    if (error || !a) throw new Error("Alert not found");
    const key = process.env['LOVABLE_API_KEY'];
    if (!key) throw new Error("AI is not configured");
    const sys = "You are a SOC analyst assistant for insider-threat detection. Write a concise briefing (max 120 words) in plain English: what happened, why it is suspicious versus the user's baseline, and 2-3 concrete next steps. No markdown headings. Do not invent facts beyond the data.";
    const payload = JSON.stringify({ employee: a.employees, date: a.date, risk_score: a.risk_score, risk_level: a.risk_level, anomaly_score: a.anomaly_score, reasons: (a.reasons as { text: string; severity: number }[]).map((r) => ({ text: r.text, severity: r.severity })), features: a.features });
    const res = await fetch("https://ai.gateway.lovable.dev/v1/responses", {
      method: "POST",
      headers: { "Lovable-API-Key": key, "Content-Type": "application/json", "X-Lovable-AIG-SDK": "fetch" },
      body: JSON.stringify({ model: "openai/gpt-6-astra", instructions: sys, input: payload, reasoning: { effort: "low" }, store: false, stream: true }),
    });
    if (res.status === 429) throw new Error("AI rate limit reached, try again shortly.");
    if (res.status === 402) throw new Error("AI credits exhausted. Add credits in workspace settings.");
    if (!res.ok || !res.body) throw new Error("AI request failed");
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "", text = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split("\n"); buf = lines.pop() ?? "";
      for (const l of lines) {
        if (!l.startsWith("data:")) continue;
        try { const ev = JSON.parse(l.slice(5)); if (ev.type === "response.output_text.delta") text += ev.delta; } catch { /* ignore */ }
      }
    }
    return { summary: text.trim() };
  });
