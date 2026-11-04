import { describe, it, expect } from "vitest";
import { parseCert, parseCertDate } from "./cert-import";

describe("CERT import", () => {
  it("parses MM/DD/YYYY dates", () => expect(parseCertDate("01/02/2010 06:49:00")).toBe("2010-01-02T06:49:00Z"));
  it("maps logon rows to login/logout", () => {
    const r = parseCert("id,date,user,pc,activity\n{A},01/02/2010 06:49:00,DTAA/ACM2278,PC-1,Logon\n{B},01/02/2010 17:00:00,DTAA/ACM2278,PC-1,Logoff");
    expect(r.kind).toBe("logon");
    expect(r.events.map((e) => e.activity)).toEqual(["login", "logout"]);
    expect(r.events[0]?.employee_id).toBe("ACM2278");
  });
  it("maps device connect to usb_connect", () => {
    expect(parseCert("id,date,user,pc,activity\n{A},01/02/2010 07:00:00,ACM2278,PC-1,Connect").events[0]?.activity).toBe("usb_connect");
  });
  it("maps file rows to downloads and skips bad dates", () => {
    const r = parseCert('id,date,user,pc,filename,content\n{A},01/02/2010 07:00:00,ACM2278,PC-1,X.doc,"a, b"\n{B},bad,ACM2278,PC-1,Y.doc,z');
    expect(r.events.map((e) => e.activity)).toEqual(["file_download"]);
    expect(r.skipped).toBe(1);
  });
});
