"use client";

import { CheckCircle2, Loader2, Siren } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { RunEvent } from "@/lib/types";

interface Row {
  cred_id: string;
  status: "validating" | "staged_healthy" | "staged_unhealthy";
  attempts: number;
  escalation?: string;
}

function derive(events: RunEvent[]): Row[] {
  const byId = new Map<string, Row>();
  for (const e of events) {
    if (e.type === "staging_attempt" && e.cred_id) {
      const r = byId.get(e.cred_id) ?? { cred_id: e.cred_id, status: "validating", attempts: 0 };
      r.attempts = Math.max(r.attempts, e.attempt ?? r.attempts);
      byId.set(e.cred_id, r);
    } else if (e.type === "staging_result" && e.cred_id) {
      const r = byId.get(e.cred_id) ?? { cred_id: e.cred_id, status: "validating", attempts: 0 };
      r.status = (e.status as Row["status"]) ?? "validating";
      r.attempts = e.attempts ?? r.attempts;
      byId.set(e.cred_id, r);
    } else if (e.type === "escalation" && e.cred_id && e.stage === "staging") {
      const r = byId.get(e.cred_id) ?? { cred_id: e.cred_id, status: "staged_unhealthy", attempts: 0 };
      r.escalation = e.reason;
      byId.set(e.cred_id, r);
    }
  }
  return [...byId.values()];
}

export function StagingPanel({ events }: { events: RunEvent[] }) {
  const rows = derive(events);
  if (rows.length === 0) return null;

  return (
    <Card className="shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CheckCircle2 className="size-5 text-primary" /> Staging &amp; validation
        </CardTitle>
        <CardDescription>
          Replacements staged alongside the live credential — nothing cut over yet.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        {rows.map((r) => (
          <div key={r.cred_id} className="rounded-lg border p-3">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-sm">{r.cred_id}</span>
              {r.status === "staged_healthy" ? (
                <Badge className="gap-1 border-transparent bg-emerald-500 text-white">
                  <CheckCircle2 className="size-3" /> staged · healthy
                </Badge>
              ) : r.status === "staged_unhealthy" ? (
                <Badge className="gap-1 border-transparent bg-amber-500 text-white">
                  <Siren className="size-3" /> escalated
                </Badge>
              ) : (
                <Badge variant="secondary" className="gap-1">
                  <Loader2 className="size-3 animate-spin" /> validating
                </Badge>
              )}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {r.attempts} attempt{r.attempts === 1 ? "" : "s"}
              {r.escalation ? ` · ${r.escalation}` : ""}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
