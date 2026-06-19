"use client";

import { FileText, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { RunEvent } from "@/lib/types";

// Which count chips to show, in order, with a tone.
const STATS: { key: string; label: string; tone: string }[] = [
  { key: "discovered", label: "discovered", tone: "bg-slate-100 text-slate-700" },
  { key: "deferred", label: "deferred", tone: "bg-slate-100 text-slate-700" },
  { key: "cut_over", label: "cut over", tone: "bg-emerald-100 text-emerald-700" },
  { key: "rolled_back", label: "rolled back", tone: "bg-amber-100 text-amber-700" },
  { key: "escalated", label: "escalated", tone: "bg-rose-100 text-rose-700" },
  { key: "staged", label: "staged", tone: "bg-indigo-100 text-indigo-700" },
];

export function ReportPanel({ events }: { events: RunEvent[] }) {
  const report = events.find((e) => e.type === "report_ready");
  if (!report) return null;
  const counts = report.counts ?? {};

  return (
    <Card data-testid="report-panel" className="border-primary/30 shadow-sm">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="size-5 text-primary" /> Run report
          {report.source === "nebius" ? (
            <Badge className="ml-auto gap-1 border-transparent bg-primary text-[10px] text-primary-foreground">
              <Sparkles className="size-3" /> Nebius AI
            </Badge>
          ) : (
            <Badge variant="secondary" className="ml-auto text-[10px] font-normal">
              fallback
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="font-medium">{report.headline}</p>
        <p className="text-sm text-muted-foreground">{report.narrative}</p>
        <div className="flex flex-wrap gap-1.5 pt-1">
          {STATS.filter((s) => (counts[s.key] ?? 0) > 0).map((s) => (
            <span key={s.key} className={`rounded-full px-2.5 py-1 text-xs font-medium ${s.tone}`}>
              {counts[s.key]} {s.label}
            </span>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
