import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import type { Reason } from "./scoring";

export type ScoreRow = {
  id: string; employee_id: string; date: string; anomaly_score: number; risk_score: number;
  risk_level: string; reasons: Reason[]; features: Record<string, number>; status: string;
  employees?: { full_name: string; department: string; role: string } | null;
};

async function all<T>(build: (from: number, to: number) => PromiseLike<{ data: T[] | null; error: { message: string } | null }>) {
  const out: T[] = [];
  for (let from = 0; ; from += 1000) {
    const { data, error } = await build(from, from + 999);
    if (error) throw new Error(error.message);
    out.push(...(data ?? []));
    if (!data || data.length < 1000) break;
  }
  return out;
}

export const scoresQuery = queryOptions({
  queryKey: ["scores"],
  queryFn: () =>
    all<ScoreRow>((a, b) =>
      supabase.from("risk_scores").select("*, employees(full_name, department, role)").order("risk_score", { ascending: false }).range(a, b) as never,
    ),
});

export const employeesQuery = queryOptions({
  queryKey: ["employees"],
  queryFn: async () => {
    const { data, error } = await supabase.from("employees").select("*").order("id");
    if (error) throw new Error(error.message);
    return data;
  },
});

export const eventTrendQuery = queryOptions({
  queryKey: ["event-trend"],
  queryFn: async () => {
    const rows = await all<{ ts: string; activity: string }>((a, b) => supabase.from("events").select("ts, activity").order("id").range(a, b) as never);
    const map = new Map<string, { logins: number; files: number; usb: number; failed: number }>();
    for (const r of rows) {
      const d = r.ts.slice(0, 10);
      const m: { logins: number; files: number; usb: number; failed: number } = map.get(d) ?? { logins: 0, files: 0, usb: 0, failed: 0 };
      if (r.activity === "login") m.logins++;
      else if (r.activity.startsWith("file")) m.files++;
      else if (r.activity.startsWith("usb")) m.usb++;
      else if (r.activity === "login_failed") m.failed++;
      map.set(d, m);
    }
    return [...map.entries()].sort().map(([date, v]) => ({ date: date.slice(5), ...v }));
  },
});

export const alertQuery = (id: string) =>
  queryOptions({
    queryKey: ["alert", id],
    queryFn: async () => {
      const { data, error } = await supabase.from("risk_scores").select("*, employees(*)").eq("id", id).single();
      if (error) throw new Error(error.message);
      return data as unknown as ScoreRow & { employees: Record<string, string | number> };
    },
  });

export const eventsByIdsQuery = (ids: number[]) =>
  queryOptions({
    queryKey: ["events-ids", ids.slice(0, 300).join(",")],
    queryFn: async () => {
      if (!ids.length) return [];
      const { data, error } = await supabase.from("events").select("*").in("id", ids.slice(0, 300)).order("ts");
      if (error) throw new Error(error.message);
      return data;
    },
  });

export const employeeDetailQuery = (id: string) =>
  queryOptions({
    queryKey: ["employee", id],
    queryFn: async () => {
      const [emp, scores, events] = await Promise.all([
        supabase.from("employees").select("*").eq("id", id).single(),
        supabase.from("risk_scores").select("*").eq("employee_id", id).order("date"),
        supabase.from("events").select("*").eq("employee_id", id).order("ts", { ascending: false }).limit(50),
      ]);
      if (emp.error) throw new Error(emp.error.message);
      const devices = await supabase.from("events").select("device").eq("employee_id", id).limit(1000);
      return {
        employee: emp.data,
        scores: (scores.data ?? []) as unknown as ScoreRow[],
        events: events.data ?? [],
        devices: [...new Set((devices.data ?? []).map((d) => d.device))],
      };
    },
  });
