import { IsolationForest } from "./isolation-forest";

export type RawEvent = {
  id: number;
  employee_id: string;
  ts: string;
  activity: string;
  device: string;
  ip: string;
  location: string;
};
export type Employee = {
  id: string;
  normal_login_start: number;
  normal_login_end: number;
  normal_download_count: number;
  home_location: string;
  primary_device: string;
};

export const FEATURE_NAMES = [
  "first_login_hour", "off_hours_events", "failed_logins", "downloads", "download_ratio",
  "uploads", "deletes", "usb_events", "new_device", "new_location", "distinct_ips", "total_events",
] as const;
export type Features = Record<(typeof FEATURE_NAMES)[number], number>;

export type Reason = { code: string; text: string; severity: number; event_ids: number[] };

export type DayScore = {
  employee_id: string;
  date: string;
  anomaly_score: number;
  risk_score: number;
  risk_level: "Low" | "Medium" | "High";
  reasons: Reason[];
  features: Features;
};

// Thresholds — keep in sync with tests.
export const HIGH_THRESHOLD = 70;
export const MEDIUM_THRESHOLD = 40;

export function riskLevel(score: number): "Low" | "Medium" | "High" {
  if (score >= HIGH_THRESHOLD) return "High";
  if (score >= MEDIUM_THRESHOLD) return "Medium";
  return "Low";
}

// Seeded timestamps are stored as "date + hours" in UTC; treat UTC hour as the local working hour.
const hourOf = (ts: string) => new Date(ts).getUTCHours();
const dayOf = (ts: string) => ts.slice(0, 10);

export function buildFeatures(emp: Employee, events: RawEvent[], history: { devices: Set<string>; locations: Set<string> }): Features {
  const logins = events.filter((e) => e.activity === "login");
  const downloads = events.filter((e) => e.activity === "file_download").length;
  const offHours = events.filter((e) => {
    const h = hourOf(e.ts);
    return h < emp.normal_login_start - 1 || h > emp.normal_login_end + 1;
  }).length;
  return {
    first_login_hour: logins.length ? Math.min(...logins.map((e) => hourOf(e.ts))) : emp.normal_login_start,
    off_hours_events: offHours,
    failed_logins: events.filter((e) => e.activity === "login_failed").length,
    downloads,
    download_ratio: downloads / Math.max(1, emp.normal_download_count),
    uploads: events.filter((e) => e.activity === "file_upload").length,
    deletes: events.filter((e) => e.activity === "file_delete").length,
    usb_events: events.filter((e) => e.activity === "usb_connect").length,
    new_device: events.some((e) => !history.devices.has(e.device)) ? 1 : 0,
    new_location: events.some((e) => !history.locations.has(e.location)) ? 1 : 0,
    distinct_ips: new Set(events.map((e) => e.ip)).size,
    total_events: events.length,
  };
}

/** Rule-based explanation layer on top of the model. */
export function explain(emp: Employee, f: Features, events: RawEvent[], usbSeenBefore: boolean): Reason[] {
  const r: Reason[] = [];
  const ids = (pred: (e: RawEvent) => boolean) => events.filter(pred).map((e) => e.id).slice(0, 200);
  if (f.off_hours_events > 0) {
    r.push({ code: "OFF_HOURS", severity: f.off_hours_events > 10 ? 30 : 15,
      text: `${f.off_hours_events} actions outside normal hours (${emp.normal_login_start}:00–${emp.normal_login_end}:00)`,
      event_ids: ids((e) => { const h = hourOf(e.ts); return h < emp.normal_login_start - 1 || h > emp.normal_login_end + 1; }) });
  }
  if (f.download_ratio >= 3) {
    r.push({ code: "MASS_DOWNLOAD", severity: f.download_ratio >= 8 ? 35 : 20,
      text: `Download count exceeded average by ${f.download_ratio.toFixed(1)}× (${f.downloads} vs ~${emp.normal_download_count})`,
      event_ids: ids((e) => e.activity === "file_download") });
  }
  if (f.usb_events > 0 && !usbSeenBefore) {
    r.push({ code: "FIRST_USB", severity: 25, text: "First USB storage device use in 30 days", event_ids: ids((e) => e.activity.startsWith("usb")) });
  }
  if (f.new_device) r.push({ code: "NEW_DEVICE", severity: 20, text: "Activity from a never-seen device fingerprint", event_ids: ids((e) => e.device !== emp.primary_device) });
  if (f.new_location) r.push({ code: "NEW_LOCATION", severity: 20, text: "Activity from a new geographic location", event_ids: ids((e) => e.location !== emp.home_location) });
  if (f.failed_logins >= 3) r.push({ code: "FAILED_LOGINS", severity: f.failed_logins >= 6 ? 25 : 15, text: `${f.failed_logins} failed login attempts`, event_ids: ids((e) => e.activity === "login_failed") });
  if (f.deletes >= 20) r.push({ code: "MASS_DELETE", severity: 30, text: `${f.deletes} files deleted in one day`, event_ids: ids((e) => e.activity === "file_delete") });
  return r.sort((a, b) => b.severity - a.severity);
}

/** Combine model output and rule severity into a 0–100 risk score. */
export function combineRisk(normalizedModel: number, reasons: Reason[]): number {
  const ruleSeverity = Math.min(100, reasons.reduce((s, x) => s + x.severity, 0));
  return Math.round(Math.min(100, 0.6 * normalizedModel * 100 + 0.4 * ruleSeverity));
}

export function scoreAll(employees: Employee[], events: RawEvent[]): DayScore[] {
  const byEmp = new Map<string, RawEvent[]>();
  for (const e of events) (byEmp.get(e.employee_id) ?? byEmp.set(e.employee_id, []).get(e.employee_id)!).push(e);

  const rows: { emp: Employee; date: string; events: RawEvent[]; f: Features; usbBefore: boolean }[] = [];
  for (const emp of employees) {
    const evs = (byEmp.get(emp.id) ?? []).sort((a, b) => a.ts.localeCompare(b.ts));
    const days = new Map<string, RawEvent[]>();
    for (const e of evs) (days.get(dayOf(e.ts)) ?? days.set(dayOf(e.ts), []).get(dayOf(e.ts))!).push(e);
    const devices = new Set([emp.primary_device]);
    const locations = new Set([emp.home_location]);
    let usbBefore = false;
    for (const date of [...days.keys()].sort()) {
      const dayEvents = days.get(date)!;
      const f = buildFeatures(emp, dayEvents, { devices, locations });
      rows.push({ emp, date, events: dayEvents, f, usbBefore });
      for (const e of dayEvents) { devices.add(e.device); locations.add(e.location); }
      if (f.usb_events > 0) usbBefore = true;
    }
  }
  if (rows.length === 0) return [];

  const matrix = rows.map((r) => FEATURE_NAMES.map((n) => r.f[n]));
  const forest = new IsolationForest(100, 256, 42).fit(matrix);
  const raw = matrix.map((x) => forest.score(x));
  const min = Math.min(...raw), max = Math.max(...raw);

  return rows.map((r, i) => {
    const rawI = raw[i] ?? 0;
    const norm = max > min ? (rawI - min) / (max - min) : 0;
    const reasons = explain(r.emp, r.f, r.events, r.usbBefore);
    const risk = combineRisk(norm, reasons);
    return {
      employee_id: r.emp.id, date: r.date, anomaly_score: Number(rawI.toFixed(4)),
      risk_score: risk, risk_level: riskLevel(risk), reasons, features: r.f,
    };
  });
}

export function suggestedAction(level: string): string {
  if (level === "High") return "Review immediately: contact the user's manager, preserve logs and consider temporarily suspending access.";
  if (level === "Medium") return "Investigate within 24 hours: verify the activity with the user or their team lead.";
  return "No action needed. Keep monitoring.";
}
