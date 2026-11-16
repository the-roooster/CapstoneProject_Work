import { queryOptions } from "@tanstack/react-query";
import type { Reason } from "./types";
export type { ScoreRow } from "./types";
import { get } from "./api";

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
