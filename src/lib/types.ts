export type Reason = { code: string; text: string; severity: number; event_ids: number[] };

export type ScoreRow = {
  id: string; employee_id: string; date: string; anomaly_score: number; risk_score: number;
  risk_level: string; reasons: Reason[]; features: Record<string, number>; status: string;
  employees?: { full_name: string; department: string; role: string } | null;
};
