import { createFileRoute, Link } from "@tanstack/react-router";
import { ShieldAlert, Brain, ListChecks } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "SentinelAI — Insider Threat Detection Platform" },
      { name: "description", content: "Per-user behavioral baselines, Isolation Forest anomaly scoring and plain-language reasons for every alert." },
      { property: "og:title", content: "SentinelAI — Insider Threat Detection Platform" },
      { property: "og:description", content: "Spot risky insider behavior and understand exactly why it was flagged." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: Landing,
});

function Landing() {
  return (
    <main className="bg-grid min-h-screen">
      <div className="mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-16">
        <p className="font-mono text-xs uppercase tracking-[0.3em] text-primary">SentinelAI // UBA</p>
        <h1 className="mt-4 max-w-3xl text-5xl font-semibold leading-tight tracking-tight md:text-6xl">
          Catch the threat that has a badge.
        </h1>
        <p className="mt-6 max-w-xl text-lg text-muted-foreground">
          SentinelAI learns each employee's normal behavior, flags statistically unusual activity, and tells
          analysts in plain language why it was flagged.
        </p>
        <div className="mt-8 flex gap-3">
          <Button asChild size="lg"><Link to="/auth">Open analyst console</Link></Button>
        </div>
        <div className="mt-16 grid gap-px overflow-hidden rounded-md border border-border bg-border md:grid-cols-3">
          {[
            { icon: ShieldAlert, t: "Behavioral baselines", d: "Logins, file activity, USB and devices per user, per day." },
            { icon: Brain, t: "Isolation Forest", d: "Unsupervised anomaly detection, no labelled attacks needed." },
            { icon: ListChecks, t: "Explainable alerts", d: "Every risk score carries human-readable reasons and evidence." },
          ].map(({ icon: Icon, t, d }) => (
            <div key={t} className="bg-card p-6">
              <Icon className="size-5 text-primary" />
              <h3 className="mt-3 font-medium">{t}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{d}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
