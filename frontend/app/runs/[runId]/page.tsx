"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Loader2, PartyPopper, ShieldAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ActivityFeed } from "@/components/ActivityFeed";
import { ApprovalGate } from "@/components/ApprovalGate";
import { CutoverPanel } from "@/components/CutoverPanel";
import { DriftPanel } from "@/components/DriftPanel";
import { DropInImage } from "@/components/DropInImage";
import { ReportPanel } from "@/components/ReportPanel";
import { ReconciliationTable } from "@/components/ReconciliationTable";
import { RunProgress } from "@/components/RunProgress";
import { StagingPanel } from "@/components/StagingPanel";
import { submitDecisions } from "@/lib/api";
import { useRunStream } from "@/lib/useRunStream";
import type { Decision } from "@/lib/types";

const NODE_LABEL: Record<string, string> = {
  discover: "Discovering",
  list_managed: "Listing inventory",
  reconcile: "Reconciling",
  assess: "Assessing",
  prioritize: "Prioritizing",
  plan: "Planning",
  stage: "Staging",
  cutover: "Cutting over",
  report: "Reporting",
};

export default function RunDetail() {
  const params = useParams<{ runId: string }>();
  const runId = params.runId;
  const { events, reconciliation, gate, done, error } = useRunStream(runId);
  const [submitting, setSubmitting] = useState(false);

  // Friendly label for the stage currently running (latest node_update).
  let stageLabel = "Starting";
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].type === "node_update" && events[i].node) {
      stageLabel = NODE_LABEL[events[i].node as string] ?? "Working";
      break;
    }
  }

  // Once decisions are submitted, the gate is consumed until the next one arrives.
  const [consumedGateAt, setConsumedGateAt] = useState<number>(-1);
  const lastGateSeq = events.filter((e) => e.type === "gate_reached").length;
  const activeGate = gate && lastGateSeq !== consumedGateAt ? gate : null;

  const onSubmit = async (decisions: Decision[]) => {
    if (!activeGate) return;
    setSubmitting(true);
    try {
      await submitDecisions(runId, activeGate.gate, decisions);
      setConsumedGateAt(lastGateSeq);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto max-w-6xl space-y-6 p-6 sm:p-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-violet-700"
          >
            <ArrowLeft className="size-4" /> All sweeps
          </Link>
          <h1 className="mt-1 font-mono text-xl font-bold tracking-tight text-primary">
            {runId}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          {error && (
            <Badge variant="destructive" className="gap-1">
              <ShieldAlert className="size-3" /> error
            </Badge>
          )}
          {done ? (
            <Badge className="gap-1 border-transparent bg-emerald-500 text-white">
              <PartyPopper className="size-3" /> completed
            </Badge>
          ) : activeGate ? (
            <Badge className="animate-soft-pulse border-transparent bg-amber-500 text-white">
              awaiting approval
            </Badge>
          ) : (
            <Badge className="gap-1 border-transparent bg-primary text-primary-foreground">
              <Loader2 className="size-3 animate-spin" /> {stageLabel}…
            </Badge>
          )}
        </div>
      </header>

      <RunProgress events={events} done={done} />

      {/* Active gate spans full width so its credential cards are roomy + readable. */}
      {activeGate && (
        <div id="sec-gate" className="scroll-mt-24">
          <ApprovalGate gate={activeGate} submitting={submitting} onSubmit={onSubmit} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2 lg:items-start">
        <div className="space-y-6">
          <div id="sec-reconcile" className="scroll-mt-24">
            <ReconciliationTable rows={reconciliation} />
          </div>
          <div id="sec-stage" className="scroll-mt-24">
            <StagingPanel events={events} />
          </div>
          <div id="sec-cutover" className="scroll-mt-24">
            <CutoverPanel events={events} />
          </div>
          <div id="sec-report" className="scroll-mt-24">
            <ReportPanel events={events} />
          </div>
          <div id="sec-drift" className="scroll-mt-24">
            <DriftPanel events={events} />
          </div>
          {done && (
            <Card
              data-testid="run-complete"
              className="animate-fade-in-up overflow-hidden border-emerald-200 bg-emerald-50 shadow-sm"
            >
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-emerald-700">
                  <PartyPopper className="size-5" /> Sweep complete!
                </CardTitle>
              </CardHeader>
              <CardContent className="flex items-start gap-4 text-sm text-emerald-800/80">
                <DropInImage
                  src="/illustrations/complete.png"
                  alt=""
                  size={96}
                  className="animate-bob hidden shrink-0 sm:block"
                  fallback={null}
                />
                <div>
                Senty walked the whole journey: discover → reconcile → plan → gate 1 → stage → gate 2 →
                cutover → report.
                <div className="mt-3">
                  <Link
                    href="/"
                    className={buttonVariants({ variant: "outline", size: "sm" })}
                  >
                    Start another sweep
                  </Link>
                </div>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
        <div id="sec-activity" className="scroll-mt-24 lg:sticky lg:top-6 lg:self-start">
          <ActivityFeed events={events} />
        </div>
      </div>
    </main>
  );
}
