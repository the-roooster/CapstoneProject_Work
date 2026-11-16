import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import type { Reason, ScoreRow } from "./types";
export type { ScoreRow } from "./types";
import { get } from "./api";

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

export type ApiEvent = {
  event_id: number; user_id: string; timestamp: string; activity_type: string; activity: string;
  device: string; ip: string; location: string; metadata: Record<string, unknown>;
};

export type AlertDetail = {
  score_id: string; user_id: string; full_name: string; department: string; date: string;
  risk_score: number; risk_level: string; anomaly_score: number; reasons: Reason[];
  features: Record<string, number> | null; investigation_status: string; suggested_action: string;
};

export type UserDetail = {
  user_id: string; full_name: string; department: string; role: string;
  baseline: { normal_login_start: number; normal_login_end: number; normal_download_count: number; home_location: string; primary_device: string };
  risk_history: Array<{ date: string; risk_score: number; risk_level: string }>;
  recent_anomalies: Array<{ score_id: string; date: string; risk_score: number; risk_level: string }>;
  devices: string[];
};

export const alertQuery = (id: string) =>
  queryOptions({
    queryKey: ["alert", id],
    queryFn: () => get<AlertDetail>(`/alerts/${encodeURIComponent(id)}`),
  });

export const eventsByIdsQuery = (ids: number[]) =>
  queryOptions({
    queryKey: ["events-ids", ids.slice(0, 300).join(",")],
    queryFn: () => ids.length
      ? get<ApiEvent[]>(`/events/by-ids?ids=${ids.slice(0, 300).join(",")}`)
      : Promise.resolve([] as ApiEvent[]),
  });

export const employeeDetailQuery = (id: string) =>
  queryOptions({
    queryKey: ["employee", id],
    queryFn: async () => {
      const [employee, events] = await Promise.all([
        get<UserDetail>(`/users/${encodeURIComponent(id)}`),
        get<ApiEvent[]>(`/events?user_id=${encodeURIComponent(id)}&limit=50`),
      ]);
      return { employee, events };
    },
  });

export const metaQuery = queryOptions({
  queryKey: ["meta"],
  queryFn: () => get<{ scale: { medium: number; high: number } }>("/meta"),
});
