import { describe, expect, it } from "vitest";
import { topRiskyUsers } from "./top-users";

describe("topRiskyUsers", () => {
  it("keeps each employee's highest score and ranks them", () => {
    const rows = [
      { employee_id: "A", risk_score: 90 },
      { employee_id: "A", risk_score: 10 },
      { employee_id: "B", risk_score: 50 },
    ];
    expect(topRiskyUsers(rows, 6)).toEqual([rows[0], rows[2]]);
    expect(topRiskyUsers(rows, 1)).toEqual([rows[0]]);
  });

  it("preserves input order for ties and keeps the first equal-scoring row", () => {
    const rows = [
      { employee_id: "A", risk_score: 50, label: "first" },
      { employee_id: "B", risk_score: 50, label: "second" },
      { employee_id: "A", risk_score: 50, label: "later" },
    ];
    expect(topRiskyUsers(rows, 6)).toEqual([rows[0], rows[1]]);
  });
});
