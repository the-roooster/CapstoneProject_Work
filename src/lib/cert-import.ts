/** Pure parser for CERT insider-threat CSVs (logon.csv, device.csv, file.csv). */
export type CertKind = "logon" | "device" | "file";
export type ParsedEvent = { employee_id: string; ts: string; activity: string; device: string; ip: string; location: string; metadata: Record<string, string> };

export const MAX_ROWS_PER_FILE = 50000;

function splitLine(line: string): string[] {
  const out: string[] = [];
  let cur = "", q = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (q) {
      if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (c === '"') q = false;
      else cur += c;
    } else if (c === '"') q = true;
    else if (c === ",") { out.push(cur); cur = ""; }
    else cur += c;
  }
  out.push(cur);
  return out;
}

/** CERT dates look like "01/02/2010 06:49:00" (MM/DD/YYYY). */
export function parseCertDate(s: string): string | null {
  const m = s.trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{4}) (\d{1,2}):(\d{2}):(\d{2})$/);
  if (!m) return null;
  const [, mo = "", d = "", y, h = "", mi, se] = m;
  return `${y}-${mo.padStart(2, "0")}-${d.padStart(2, "0")}T${h.padStart(2, "0")}:${mi}:${se}Z`;
}

export function detectKind(header: string[], sampleActivity = ""): CertKind | null {
  const h = header.map((x) => x.trim().toLowerCase());
  if (!h.includes("date") || !h.includes("user")) return null;
  if (h.includes("filename")) return "file";
  const a = sampleActivity.trim().toLowerCase();
  if (a === "logon" || a === "logoff") return "logon";
  if (a === "connect" || a === "disconnect") return "device";
  return null;
}

export function mapActivity(kind: CertKind, raw: string, filename = ""): string | null {
  const a = raw.trim().toLowerCase();
  if (kind === "logon") return a === "logon" ? "login" : a === "logoff" ? "logout" : null;
  if (kind === "device") return a === "connect" ? "usb_connect" : a === "disconnect" ? "usb_disconnect" : null;
  if (a.includes("delete")) return "file_delete";
  if (a.includes("open")) return "file_open";
  return filename || a ? "file_download" : null; // copy/write (to removable media) = exfil signal
}

export function parseCert(text: string, kindHint?: CertKind): { kind: CertKind; events: ParsedEvent[]; skipped: number } {
  const lines = text.split(/\r?\n/).filter((l) => l.trim());
  const header = splitLine(lines[0] ?? "").map((x) => x.trim().toLowerCase());
  const kind = kindHint ?? detectKind(header, splitLine(lines[1] ?? "")[header.indexOf("activity")] ?? "");
  if (!kind) throw new Error("Unrecognised CSV: expected CERT logon, device or file columns (date, user, pc, ...)");
  const col = (n: string) => header.indexOf(n);
  const [iDate, iUser, iPc, iAct, iFile] = [col("date"), col("user"), col("pc"), col("activity"), col("filename")];
  if (iDate < 0 || iUser < 0) throw new Error("CSV is missing 'date' or 'user' columns");
  const events: ParsedEvent[] = [];
  let skipped = 0;
  for (const line of lines.slice(1, MAX_ROWS_PER_FILE + 1)) {
    const r = splitLine(line);
    const ts = parseCertDate(r[iDate] ?? "");
    const user = (r[iUser] ?? "").trim().split("/").pop() ?? "";
    const filename = iFile >= 0 ? (r[iFile] ?? "") : "";
    const activity = mapActivity(kind, iAct >= 0 ? r[iAct] ?? "" : "", filename);
    if (!ts || !user || !activity) { skipped++; continue; }
    events.push({
      employee_id: user, ts, activity, device: (r[iPc] ?? "unknown").trim() || "unknown",
      ip: "0.0.0.0", location: "Unknown", metadata: { source: `cert:${kind}`, ...(filename ? { filename } : {}) },
    });
  }
  return { kind, events, skipped };
}
