"use client";

import { CircleCheck, KeyRound, ShieldAlert, ShieldOff, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { Routing } from "@/lib/types";

const ROUTING_STYLE: Record<
  Routing,
  { label: string; row: string; badge: string; icon: LucideIcon; iconColor: string }
> = {
  DEFER: {
    label: "DEFER",
    row: "bg-white/[0.02] text-white/78",
    badge: "border-white/15 bg-white/10 text-white/74",
    icon: CircleCheck,
    iconColor: "text-sky-200/70",
  },
  OWN_UNMANAGED: {
    label: "OWN · UNMANAGED",
    row: "bg-lime-300/[0.055] text-white",
    badge: "border-lime-300/35 bg-lime-300 text-black",
    icon: ShieldAlert,
    iconColor: "text-lime-300",
  },
  OWN_STALE: {
    label: "OWN · STALE",
    row: "bg-amber-400/[0.075] text-white",
    badge: "border-amber-300/35 bg-amber-400 text-black",
    icon: ShieldOff,
    iconColor: "text-amber-300",
  },
  UNKNOWN: {
    label: "UNKNOWN COVERAGE",
    row: "bg-rose-500/[0.09] text-white",
    badge: "border-rose-300/30 bg-rose-500 text-white",
    icon: ShieldAlert,
    iconColor: "text-rose-300",
  },
};

export function ReconciliationTable({
  rows,
}: {
  rows: { cred_id: string; label: string; routing: Routing }[];
}) {
  return (
    <Card className="border-white/10 bg-card/85 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-5 text-primary" /> Coverage reconciliation
        </CardTitle>
        <CardDescription>
          Managed-and-rotating credentials are <strong>deferred</strong>; the unmanaged tail is{" "}
          <strong>owned</strong>.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-hidden rounded-xl border border-white/10 bg-black/10">
          <table className="w-full text-sm">
            <thead className="bg-white/[0.035] text-left text-xs uppercase text-white/58">
              <tr>
                <th className="px-3 py-2 font-medium">Credential</th>
                <th className="px-3 py-2 font-medium">ID</th>
                <th className="px-3 py-2 font-medium">Routing</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-3 py-8 text-center text-muted-foreground">
                    <span className="animate-soft-pulse">Scanning production for live credentials…</span>
                  </td>
                </tr>
              )}
              {rows.map((r) => {
                const style = ROUTING_STYLE[r.routing] ?? ROUTING_STYLE.UNKNOWN;
                const Icon = style.icon;
                return (
                  <tr
                    key={r.cred_id}
                    data-testid={`recon-row-${r.cred_id}`}
                    data-routing={r.routing}
                    className={cn("animate-fade-in-up border-t border-white/10", style.row)}
                  >
                    <td className="px-3 py-2.5">
                      <span className="flex items-center gap-2 font-medium">
                        <Icon className={cn("size-4 shrink-0", style.iconColor)} />
                        {r.label}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs text-white/58">
                      {r.cred_id}
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge className={cn("border-transparent", style.badge)}>{style.label}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
