"use client";

import { ArrowRight, History, Sparkle, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { RunEvent } from "@/lib/types";

export function DriftPanel({ events }: { events: RunEvent[] }) {
  const drift = events.find((e) => e.type === "drift_summary");
  if (!drift) return null;

  const total = (drift.new?.length ?? 0) + (drift.changed?.length ?? 0) + (drift.stuck?.length ?? 0);

  return (
    <Card data-testid="drift-panel" className="shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <History className="size-5 text-primary" /> Coverage drift
        </CardTitle>
        <CardDescription>
          {drift.first_run
            ? "First sweep — nothing to compare against yet."
            : `Compared against the prior sweep (${drift.prior_run_id}).`}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        {drift.first_run ? (
          <p className="text-muted-foreground">Run another sweep to see what changed across cycles.</p>
        ) : total === 0 ? (
          <p className="text-muted-foreground">No coverage drift since the last sweep.</p>
        ) : (
          <>
            {!!drift.new?.length && (
              <div>
                <div className="mb-1 flex items-center gap-1.5 font-medium text-emerald-700">
                  <Sparkle className="size-3.5" /> Newly discovered ({drift.new.length})
                </div>
                <ul className="space-y-0.5 text-muted-foreground">
                  {drift.new.map((d) => (
                    <li key={d.cred_id} className="font-mono text-xs">
                      {d.cred_id} — {d.routing}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {!!drift.changed?.length && (
              <div>
                <div className="mb-1 flex items-center gap-1.5 font-medium text-amber-700">
                  <RefreshCw className="size-3.5" /> Coverage changed ({drift.changed.length})
                </div>
                <ul className="space-y-0.5 text-muted-foreground">
                  {drift.changed.map((d) => (
                    <li key={d.cred_id} className="flex items-center gap-1.5 font-mono text-xs">
                      {d.cred_id}: {d.from} <ArrowRight className="size-3" /> {d.to}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {!!drift.stuck?.length && (
              <div>
                <div className="mb-1 flex items-center gap-1.5 font-medium text-rose-700">
                  <History className="size-3.5" /> Stuck across cycles ({drift.stuck.length})
                </div>
                <ul className="space-y-0.5 text-muted-foreground">
                  {drift.stuck.map((d) => (
                    <li key={d.cred_id} className="font-mono text-xs">
                      {d.cred_id} — still {d.disposition}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
        <Badge variant="secondary" className="font-normal">
          cross-run memory
        </Badge>
      </CardContent>
    </Card>
  );
}
