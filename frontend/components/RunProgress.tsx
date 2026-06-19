"use client";

import {
  ClipboardCheck,
  FileText,
  GitCompare,
  PackageCheck,
  Radar,
  ScanLine,
  ShieldQuestion,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { RunEvent } from "@/lib/types";

interface Stage {
  key: string;
  label: string;
  icon: LucideIcon;
  target: string; // DOM id of the panel this step jumps to
  reached: (e: RunEvent[]) => boolean;
}

const has = (events: RunEvent[], pred: (e: RunEvent) => boolean) => events.some(pred);
const sawNode = (events: RunEvent[], node: string) =>
  has(events, (e) => e.type === "node_update" && e.node === node);

const STAGES: Stage[] = [
  { key: "discover", label: "Discover", icon: Radar, target: "sec-activity", reached: (e) => sawNode(e, "discover") },
  { key: "reconcile", label: "Reconcile", icon: GitCompare, target: "sec-reconcile", reached: (e) => sawNode(e, "reconcile") },
  { key: "plan", label: "Plan", icon: ScanLine, target: "sec-gate", reached: (e) => sawNode(e, "plan") },
  { key: "gate1", label: "Gate 1", icon: ShieldQuestion, target: "sec-gate", reached: (e) => has(e, (x) => x.type === "gate_reached" && x.gate === "staging") },
  { key: "stage", label: "Stage", icon: PackageCheck, target: "sec-stage", reached: (e) => has(e, (x) => x.type === "staging_result") },
  { key: "gate2", label: "Gate 2", icon: ClipboardCheck, target: "sec-gate", reached: (e) => has(e, (x) => x.type === "gate_reached" && x.gate === "cutover") },
  { key: "cutover", label: "Cutover", icon: Zap, target: "sec-cutover", reached: (e) => has(e, (x) => x.type === "cutover_step") },
  { key: "report", label: "Report", icon: FileText, target: "sec-report", reached: (e) => sawNode(e, "report") || has(e, (x) => x.type === "run_completed") },
];

function jumpTo(id: string) {
  // Fall back to the activity feed if the panel isn't on the page yet/anymore
  // (e.g., an approval gate that's already been cleared).
  const el = document.getElementById(id) ?? document.getElementById("sec-activity");
  el?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function RunProgress({ events, done }: { events: RunEvent[]; done: boolean }) {
  const reached = STAGES.map((s) => s.reached(events));
  const lastReached = reached.lastIndexOf(true);
  const activeIdx = done ? -1 : Math.min(lastReached + 1, STAGES.length - 1);

  return (
    <div className="flex items-center justify-between gap-1 overflow-x-auto rounded-2xl border bg-card p-3 shadow-sm">
      {STAGES.map((s, i) => {
        const isDone = reached[i] && (i < lastReached || done || i !== activeIdx);
        const isActive = i === activeIdx && !done;
        const Icon = s.icon;
        return (
          <div key={s.key} className="flex flex-1 items-center">
            <button
              type="button"
              onClick={() => jumpTo(s.target)}
              title={`Jump to ${s.label}`}
              className="group flex min-w-14 cursor-pointer flex-col items-center gap-1 rounded-lg p-1 transition-colors hover:bg-muted"
            >
              <div
                className={cn(
                  "flex size-10 items-center justify-center rounded-full border-2 transition-all group-hover:scale-105",
                  isDone && "border-primary bg-primary text-primary-foreground",
                  isActive && "animate-soft-pulse border-primary bg-primary/10 text-primary",
                  !isDone && !isActive && "border-dashed border-border text-muted-foreground/40 group-hover:border-primary/40 group-hover:text-primary",
                )}
              >
                <Icon className="size-5" />
              </div>
              <span
                className={cn(
                  "text-[11px] font-medium",
                  isDone || isActive ? "text-foreground" : "text-muted-foreground/50",
                  "group-hover:text-primary",
                )}
              >
                {s.label}
              </span>
            </button>
            {i < STAGES.length - 1 && (
              <div
                className={cn(
                  "mx-0.5 h-0.5 flex-1 rounded-full transition-colors",
                  reached[i + 1] || (isDone && reached[i]) ? "bg-primary" : "bg-border",
                )}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
