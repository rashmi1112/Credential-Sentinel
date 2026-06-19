"use client";

import { useEffect, useRef } from "react";
import {
  Activity,
  AlertTriangle,
  ClipboardList,
  FileText,
  Gauge,
  GitCompare,
  History,
  PartyPopper,
  PackageCheck,
  Radar,
  ScanLine,
  ShieldQuestion,
  Siren,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { RunEvent } from "@/lib/types";

const STYLE: Record<string, { icon: LucideIcon; tone: string; label: string }> = {
  node_update: { icon: Radar, tone: "text-muted-foreground", label: "node" },
  reconciliation_item: { icon: GitCompare, tone: "text-muted-foreground", label: "reconcile" },
  assessment_item: { icon: ScanLine, tone: "text-muted-foreground", label: "assess" },
  urgency_item: { icon: Gauge, tone: "text-muted-foreground", label: "urgency" },
  plan_drafted: { icon: ClipboardList, tone: "text-primary", label: "plan" },
  gate_reached: { icon: ShieldQuestion, tone: "text-primary", label: "gate" },
  staging_attempt: { icon: PackageCheck, tone: "text-muted-foreground", label: "staging" },
  staging_result: { icon: PackageCheck, tone: "text-muted-foreground", label: "staging" },
  escalation: { icon: Siren, tone: "text-amber-600", label: "escalate" },
  cutover_step: { icon: Zap, tone: "text-muted-foreground", label: "cutover" },
  cutover_result: { icon: Zap, tone: "text-primary", label: "cutover" },
  drift_summary: { icon: History, tone: "text-primary", label: "drift" },
  report_ready: { icon: FileText, tone: "text-primary", label: "report" },
  run_completed: { icon: PartyPopper, tone: "text-emerald-600", label: "done" },
  error: { icon: AlertTriangle, tone: "text-rose-600", label: "error" },
};

function line(ev: RunEvent): string {
  switch (ev.type) {
    case "node_update":
      return `[${ev.node}] ${ev.message}`;
    case "reconciliation_item":
      return `${ev.label} → ${ev.routing}`;
    case "assessment_item":
      return `${ev.label}: ${ev.expired ? "EXPIRED" : `${ev.days_to_expiry}d left`}${ev.expiry_source === "real_tls" ? " (live TLS)" : ""}, ${ev.consumer_count} consumer(s)${ev.safe_to_rotate ? "" : " — BLOCKED"}`;
    case "urgency_item":
      return `${ev.label}: urgency ${ev.score}/100 (${ev.band})`;
    case "plan_drafted":
      return `Plan for ${ev.label} [${ev.source}]: ${ev.impact_summary}`;
    case "gate_reached":
      return `Gate reached: ${ev.gate} (${ev.payload?.items.length ?? 0} item(s) awaiting approval)`;
    case "staging_attempt":
      return `Staging ${ev.cred_id} — attempt ${ev.attempt}: ${ev.status}`;
    case "staging_result":
      return `Staged ${ev.cred_id}: ${ev.status}${ev.attempts ? ` (${ev.attempts} attempt(s))` : ""}`;
    case "escalation":
      return `Escalated ${ev.cred_id} at ${ev.stage}: ${ev.reason}`;
    case "cutover_step":
      return `${ev.cred_id} — ${ev.step}: ${ev.status}`;
    case "cutover_result":
      return `${ev.cred_id}: ${ev.status === "cutover_complete" ? "cut over — old credential revoked" : "rolled back — old credential retained"}`;
    case "drift_summary":
      return ev.first_run
        ? "Coverage drift: first sweep — no prior run to compare"
        : `Coverage drift vs prior: ${ev.new?.length ?? 0} new, ${ev.changed?.length ?? 0} changed, ${ev.stuck?.length ?? 0} stuck`;
    case "report_ready":
      return `Report: ${ev.headline}`;
    case "run_completed":
      return "Run completed.";
    case "error":
      return `Error: ${ev.message}`;
    default:
      return JSON.stringify(ev);
  }
}

export function ActivityFeed({ events }: { events: RunEvent[] }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  // Auto-scroll the feed's own viewport (not the window) to the newest event.
  useEffect(() => {
    const vp = wrapRef.current?.querySelector<HTMLElement>('[data-slot="scroll-area-viewport"]');
    if (vp) vp.scrollTo({ top: vp.scrollHeight, behavior: "smooth" });
  }, [events.length]);

  return (
    <Card className="shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span className="animate-soft-pulse size-2.5 rounded-full bg-emerald-500" />
          Activity feed
          <Badge variant="secondary" className="ml-auto font-normal">
            <Activity className="mr-1 size-3" />
            {events.length}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div ref={wrapRef}>
        <ScrollArea className="thin-scroll h-[68vh] pr-4">
          <ol className="space-y-0.5">
            {events.length === 0 && (
              <li className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
                <Radar className="size-4" /> Waiting for Senty to report in…
              </li>
            )}
            {events.map((ev, i) => {
              const s = STYLE[ev.type] ?? STYLE.node_update;
              const Icon = s.icon;
              return (
                <li
                  key={ev.seq ?? i}
                  className="animate-fade-in-up flex items-start gap-2 rounded-lg px-2 py-1.5 hover:bg-muted"
                >
                  <Icon className={cn("mt-0.5 size-4 shrink-0", s.tone)} />
                  <span className="w-16 shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                    {s.label}
                  </span>
                  <span
                    className={cn(
                      "font-mono text-xs leading-5",
                      ev.type === "error" && "font-medium text-rose-600",
                      ev.type === "run_completed" && "font-medium text-emerald-700",
                    )}
                  >
                    {line(ev)}
                  </span>
                </li>
              );
            })}
          </ol>
        </ScrollArea>
        </div>
      </CardContent>
    </Card>
  );
}
