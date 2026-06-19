"use client";

import { useState } from "react";
import { Ban, Check, ClipboardCheck, Radio, ShieldQuestion, Sparkles, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import type { Decision, DecisionAction, GatePayload } from "@/lib/types";

const GATE_COPY: Record<
  string,
  { title: string; desc: string; header: string; submit: string; icon: typeof ShieldQuestion }
> = {
  staging: {
    title: "Gate 1 — Approve staging",
    desc: "Approve which credentials may have a replacement staged and validated. Nothing live is touched.",
    header: "bg-amber-500",
    submit: "bg-amber-500 text-black hover:bg-amber-400",
    icon: ShieldQuestion,
  },
  cutover: {
    title: "Gate 2 — Approve cutover",
    desc: "Approve each cutover. The old credential is revoked only after the new one is verified healthy.",
    header: "bg-primary",
    submit: "bg-primary text-primary-foreground hover:bg-primary/90",
    icon: Zap,
  },
};

const BAND_BADGE: Record<string, string> = {
  critical: "bg-rose-500 text-white",
  high: "bg-orange-500 text-white",
  medium: "bg-amber-500 text-white",
  low: "bg-slate-300 text-slate-700",
};

export function ApprovalGate({
  gate,
  submitting,
  onSubmit,
}: {
  gate: GatePayload;
  submitting: boolean;
  onSubmit: (decisions: Decision[]) => void;
}) {
  // No default: the human must make an explicit call on every credential. A
  // safety gate shouldn't bias toward approve.
  const [choices, setChoices] = useState<Record<string, DecisionAction | undefined>>({});
  const copy = GATE_COPY[gate.gate] ?? {
    title: `Gate — ${gate.gate}`,
    desc: "",
    header: "bg-primary",
    submit: "bg-primary text-primary-foreground hover:bg-primary/90",
    icon: ClipboardCheck,
  };
  const HeaderIcon = copy.icon;

  const set = (id: string, action: DecisionAction) =>
    setChoices((prev) => ({ ...prev, [id]: action }));

  const allDecided = gate.items.every((i) => choices[i.cred_id]);
  const decidedCount = gate.items.filter((i) => choices[i.cred_id]).length;

  const submit = () =>
    onSubmit(
      gate.items.map((i) => ({ cred_id: i.cred_id, action: choices[i.cred_id] as DecisionAction })),
    );

  return (
    <div
      data-testid="approval-gate"
      data-gate={gate.gate}
      className="animate-fade-in-up overflow-hidden rounded-xl border bg-card text-sm text-card-foreground shadow-sm"
    >
      <div className={cn("p-5 text-primary-foreground", copy.header)}>
        <div className="flex items-center gap-2 text-lg font-bold">
          <HeaderIcon className="size-5" /> {copy.title}
          <Badge className="ml-auto border-black/20 bg-black/10 text-primary-foreground">
            {gate.items.length} pending
          </Badge>
        </div>
        <p className="mt-1 text-sm text-primary-foreground/75">{copy.desc}</p>
      </div>

      <div className="space-y-3 p-5">
        {gate.items.map((item) => {
          const choice = choices[item.cred_id];
          return (
            <div key={item.cred_id} data-testid={`gate-item-${item.cred_id}`}>
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2 text-base font-semibold">
                    {item.label}
                    {item.urgency && (
                      <Badge
                        className={cn("border-transparent text-xs", BAND_BADGE[item.urgency.band])}
                      >
                        {item.urgency.band} · {item.urgency.score}
                      </Badge>
                    )}
                  </div>
                  <div className="font-mono text-sm text-muted-foreground">
                    {item.cred_id} · {item.proposed_action}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    data-testid={`approve-${item.cred_id}`}
                    variant={choice === "approve" ? "default" : "outline"}
                    onClick={() => set(item.cred_id, "approve")}
                    disabled={submitting}
                    className={cn(
                      "gap-1",
                      choice === "approve" && "bg-emerald-500 text-white hover:bg-emerald-600",
                    )}
                  >
                    <Check className="size-3.5" /> Approve
                  </Button>
                  <Button
                    size="sm"
                    data-testid={`reject-${item.cred_id}`}
                    variant={choice === "reject" ? "destructive" : "outline"}
                    onClick={() => set(item.cred_id, "reject")}
                    disabled={submitting}
                    className="gap-1"
                  >
                    <Ban className="size-3.5" /> Reject
                  </Button>
                </div>
              </div>

              {(item.urgency || item.plan) && (
                <div className="mt-2 rounded-lg border bg-muted/40 p-3 text-sm">
                  {(item.days_to_expiry !== undefined || item.consumer_count !== undefined) && (
                    <div className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
                      {item.days_to_expiry !== undefined && (
                        <span className="inline-flex items-center gap-1.5">
                          Expiry:{" "}
                          <span className={cn("font-medium", item.expired ? "text-rose-600" : "text-foreground")}>
                            {item.expired ? "EXPIRED" : `${item.days_to_expiry} days`}
                          </span>
                          {item.not_after ? ` (${item.not_after})` : ""}
                          {item.expiry_source === "real_tls" && (
                            <Badge className="gap-1 border-transparent bg-emerald-600 text-[11px] font-medium text-white">
                              <Radio className="size-3" /> live TLS
                            </Badge>
                          )}
                        </span>
                      )}
                      {item.consumer_count !== undefined && (
                        <span>
                          Blast radius:{" "}
                          <span className="font-medium text-foreground">{item.consumer_count}</span>
                          {item.consumers?.length ? ` — ${item.consumers.join(", ")}` : ""}
                        </span>
                      )}
                    </div>
                  )}
                  {item.plan && (
                    <div>
                      <div className="mb-1 flex items-center gap-2 font-medium text-foreground">
                        Rotation plan
                        {item.plan.source === "nebius" ? (
                          <Badge
                            title={item.plan.model ?? undefined}
                            className="gap-1 border-transparent bg-primary text-xs font-medium text-primary-foreground"
                          >
                            <Sparkles className="size-3.5" /> Drafted by Nebius AI
                          </Badge>
                        ) : (
                          <Badge variant="secondary" className="text-xs font-normal">
                            Deterministic fallback
                          </Badge>
                        )}
                      </div>
                      <ol className="ml-4 list-decimal space-y-0.5 text-muted-foreground">
                        {item.plan.steps.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ol>
                      {item.plan.impact_summary && (
                        <p className="mt-1.5 text-muted-foreground">
                          <span className="font-medium text-foreground">Impact:</span>{" "}
                          {item.plan.impact_summary}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}
              <Separator className="mt-3" />
            </div>
          );
        })}
        <Button
          onClick={submit}
          disabled={submitting || !allDecided}
          data-testid="submit-decisions"
          className={cn(
            "h-11 w-full text-base font-medium",
            allDecided ? copy.submit : "bg-muted-foreground/40 text-foreground",
          )}
        >
          {submitting
            ? "Resuming…"
            : allDecided
              ? "Submit decisions & resume"
              : `Decide on each credential (${decidedCount}/${gate.items.length})`}
        </Button>
      </div>
    </div>
  );
}
