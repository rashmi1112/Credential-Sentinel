"use client";

import { CheckCircle2, RotateCcw, XCircle, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { RunEvent } from "@/lib/types";

const STEP_LABEL: Record<string, string> = {
  promote: "Promote new credential",
  repoint: "Repoint consumers",
  verify: "Verify consumer health",
  revoke_old: "Revoke old credential (delayed)",
  rollback: "Roll back to old credential",
};

interface Row {
  cred_id: string;
  steps: { step: string; status: string }[];
  result?: "cutover_complete" | "rolled_back";
}

function derive(events: RunEvent[]): Row[] {
  const byId = new Map<string, Row>();
  for (const e of events) {
    if (e.type === "cutover_step" && e.cred_id) {
      const r = byId.get(e.cred_id) ?? { cred_id: e.cred_id, steps: [] };
      r.steps.push({ step: e.step ?? "", status: e.status ?? "ok" });
      byId.set(e.cred_id, r);
    } else if (e.type === "cutover_result" && e.cred_id) {
      const r = byId.get(e.cred_id) ?? { cred_id: e.cred_id, steps: [] };
      r.result = e.status as Row["result"];
      byId.set(e.cred_id, r);
    }
  }
  return [...byId.values()];
}

export function CutoverPanel({ events }: { events: RunEvent[] }) {
  const rows = derive(events);
  if (rows.length === 0) return null;

  return (
    <Card className="shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Zap className="size-5 text-primary" /> Cutover
        </CardTitle>
        <CardDescription>
          Delayed revocation — the old credential stays valid until the new one verifies healthy, so a
          failed cutover rolls back with nothing lost.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {rows.map((r) => (
          <div key={r.cred_id} className="rounded-lg border p-3">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-sm">{r.cred_id}</span>
              {r.result === "cutover_complete" ? (
                <Badge className="gap-1 border-transparent bg-emerald-500 text-white">
                  <CheckCircle2 className="size-3" /> cut over
                </Badge>
              ) : r.result === "rolled_back" ? (
                <Badge className="gap-1 border-transparent bg-amber-500 text-white">
                  <RotateCcw className="size-3" /> rolled back
                </Badge>
              ) : (
                <Badge variant="secondary">in progress…</Badge>
              )}
            </div>
            <ol className="mt-2 space-y-1">
              {r.steps.map((s, i) => {
                const failed = s.status === "failed";
                const isRollback = s.step === "rollback";
                return (
                  <li key={i} className="flex items-center gap-2 text-xs">
                    {failed ? (
                      <XCircle className="size-3.5 text-rose-500" />
                    ) : isRollback ? (
                      <RotateCcw className="size-3.5 text-amber-500" />
                    ) : (
                      <CheckCircle2 className="size-3.5 text-emerald-500" />
                    )}
                    <span className={cn(failed && "text-rose-600", isRollback && "text-amber-600")}>
                      {STEP_LABEL[s.step] ?? s.step}
                    </span>
                  </li>
                );
              })}
            </ol>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
