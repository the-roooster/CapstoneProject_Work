import { describe, expect, it } from "vitest";
import { riskLevel, scoreAll, type Employee, type RawEvent } from "./scoring";

describe("risk levels", () => {
  it("70 and above is High", () => expect(riskLevel(70)).toBe("High"));
  it("40–69 is Medium", () => { expect(riskLevel(40)).toBe("Medium"); expect(riskLevel(69)).toBe("Medium"); });
  it("below 40 is Low", () => expect(riskLevel(39)).toBe("Low"));
});

describe("scoring pipeline", () => {
  const emp: Employee = { id: "E1", normal_login_start: 9, normal_login_end: 18, normal_download_count: 10, home_location: "Pune", primary_device: "WS-1" };
  let id = 1;
  const ev = (day: string, h: number, activity: string, extra: Partial<RawEvent> = {}): RawEvent =>
    ({ id: id++, employee_id: "E1", ts: `${day}T${String(h).padStart(2, "0")}:10:00Z`, activity, device: "WS-1", ip: "10.0.0.1", location: "Pune", ...extra });
  const events: RawEvent[] = [];
  for (let d = 1; d <= 20; d++) {
    const day = `2026-01-${String(d).padStart(2, "0")}`;
    events.push(ev(day, 9, "login"));
    for (let i = 0; i < 10; i++) events.push(ev(day, 11, "file_download"));
  }
  events.push(ev("2026-01-21", 2, "login", { device: "LAPTOP-X" }));
  for (let i = 0; i < 120; i++) events.push(ev("2026-01-21", 2, "file_download", { device: "LAPTOP-X" }));
  events.push(ev("2026-01-21", 3, "usb_connect", { device: "LAPTOP-X" }));

  const scores = scoreAll([emp], events);
  const bad = scores.find((s) => s.date === "2026-01-21")!;

  it("flags the 2 AM mass-download day as High", () => expect(bad.risk_level).toBe("High"));
  it("explains it with off-hours, mass download, first USB and new device", () => {
    const codes = bad.reasons.map((r) => r.code);
    expect(codes).toEqual(expect.arrayContaining(["OFF_HOURS", "MASS_DOWNLOAD", "FIRST_USB", "NEW_DEVICE"]));
  });
  it("leaves normal days Low", () => expect(scores.filter((s) => s.date !== "2026-01-21").every((s) => s.risk_level === "Low")).toBe(true));
});
