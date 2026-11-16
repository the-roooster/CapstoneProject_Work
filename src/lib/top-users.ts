export function topRiskyUsers<T extends { employee_id: string; risk_score: number }>(rows: readonly T[], n: number): T[] {
  const highest = new Map<string, T>();
  for (const row of rows) {
    const previous = highest.get(row.employee_id);
    if (!previous || row.risk_score > previous.risk_score) {
      highest.set(row.employee_id, row);
    }
  }
  return [...highest.values()].sort((a, b) => b.risk_score - a.risk_score).slice(0, n);
}
