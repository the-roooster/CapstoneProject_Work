import { cn } from "@/lib/utils";

export function RiskBadge({ level, className }: { level: string; className?: string }) {
  const tone =
    level === "High"
      ? "border-risk-high/50 bg-risk-high/15 text-risk-high"
      : level === "Medium"
        ? "border-risk-medium/50 bg-risk-medium/15 text-risk-medium"
        : "border-risk-low/50 bg-risk-low/15 text-risk-low";
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 font-mono text-xs uppercase tracking-wider", tone, className)}>
      <span className="size-1.5 rounded-full bg-current" />
      {level}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className="rounded-sm border border-border bg-secondary px-2 py-0.5 font-mono text-xs uppercase tracking-wider text-muted-foreground">
      {status}
    </span>
  );
}

export function Panel({ title, action, children, className }: { title?: string; action?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-md border border-border bg-card", className)}>
      {title && (
        <header className="flex items-center justify-between border-b border-border px-4 py-2.5">
          <h2 className="font-mono text-xs uppercase tracking-[0.18em] text-muted-foreground">{title}</h2>
          {action}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export const riskColor = (level: string) =>
  level === "High" ? "var(--risk-high)" : level === "Medium" ? "var(--risk-medium)" : "var(--risk-low)";
