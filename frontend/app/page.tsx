"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowRight,
  ClipboardCheck,
  GitCompare,
  History,
  PackageCheck,
  Radar,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DropInImage } from "@/components/DropInImage";
import { HeroArt } from "@/components/HeroArt";
import { createRun, listRuns } from "@/lib/api";
import type { RunListItem } from "@/lib/types";

const STEPS = [
  {
    icon: Radar,
    label: "Discover",
    desc: "Finds live credentials in production — including a real TLS handshake that reads each certificate's true expiry.",
    tooltipClass: "left-0",
  },
  {
    icon: GitCompare,
    label: "Reconcile",
    desc: "Cross-references every credential against the rotation services: defer the ones actively rotated, own the unmanaged or stale tail.",
    tooltipClass: "left-0 sm:left-1/2 sm:-translate-x-1/2",
  },
  {
    icon: PackageCheck,
    label: "Stage",
    desc: "Creates and validates a replacement credential alongside the live one — nothing live is touched yet (gated by a human).",
    tooltipClass: "left-0 xl:left-1/2 xl:-translate-x-1/2",
  },
  {
    icon: ClipboardCheck,
    label: "Cutover",
    desc: "Promotes the new credential, repoints consumers, verifies health, then revokes the old one — auto-rolling back if verification fails.",
    tooltipClass: "left-0 sm:right-0 sm:left-auto",
  },
];

const LAST_EVENT_DOT: Record<string, string> = {
  run_completed: "bg-emerald-500",
  gate_reached: "bg-amber-500",
  error: "bg-rose-500",
};

function formatWhen(epochSeconds?: number): string {
  if (!epochSeconds) return "";
  return new Date(epochSeconds * 1000).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function Dashboard() {
  const router = useRouter();
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRuns().then(setRuns).catch(() => setRuns([]));
  }, []);

  const start = async () => {
    setStarting(true);
    setError(null);
    try {
      const { run_id } = await createRun();
      router.push(`/runs/${run_id}`);
    } catch {
      setError("Can't reach the backend. Is it running on :8000?");
      setStarting(false);
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute inset-0 bg-[linear-gradient(115deg,rgba(13,15,11,1)_0%,rgba(19,24,16,1)_48%,rgba(7,8,7,1)_100%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_78%_24%,rgba(212,255,71,0.18),transparent_28%),radial-gradient(circle_at_10%_86%,rgba(255,255,255,0.08),transparent_24%)]" />
        <div className="absolute inset-0 opacity-[0.12] [background-image:linear-gradient(rgba(255,255,255,0.28)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.28)_1px,transparent_1px)] [background-size:48px_48px]" />
      </div>

      <section className="relative mx-auto flex min-h-[calc(100svh-3rem)] w-full max-w-7xl items-center overflow-hidden px-6 py-8 sm:px-8 lg:py-10">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-y-0 left-[30%] right-[-18%] hidden bg-[radial-gradient(circle_at_65%_47%,rgba(212,255,71,0.2),transparent_34%),linear-gradient(90deg,rgba(7,8,7,0.9)_0%,rgba(7,8,7,0.38)_34%,rgba(7,8,7,0)_72%)] lg:block"
        />

        <div className="animate-fade-in-up relative z-10 max-w-2xl space-y-5 text-center sm:space-y-7 lg:text-left">
          <Badge className="border border-lime-300/35 bg-lime-300/10 px-3 py-1 font-mono text-[0.62rem] uppercase text-lime-200 hover:bg-lime-300/10">
            Agentic AI Systems
          </Badge>
          <div className="space-y-5">
            <h1 className="text-4xl font-semibold leading-[0.95] text-white sm:text-6xl lg:text-7xl">
              Credential <span className="block text-lime-300">Sentinel</span>
            </h1>
            <p className="mx-auto max-w-lg text-sm leading-6 text-white/68 sm:text-lg sm:leading-7 lg:mx-0">
              Find the unmanaged credentials your rotation services miss, reconcile them against the
              managed inventory, and drive safe human-approved rotations from one live sweep.
            </p>
          </div>

          <div className="flex flex-col items-center gap-3 sm:flex-row lg:items-start">
            <Button
              onClick={start}
              disabled={starting}
              size="lg"
              data-testid="start-sweep"
              className="group h-12 rounded-none border border-lime-300 bg-lime-300 px-6 text-base font-semibold text-black hover:bg-lime-200"
            >
              {starting ? "Starting sweep..." : "Start a new sweep"}
              <ArrowRight className="ml-1 size-5 transition-transform group-hover:translate-x-1" />
            </Button>
            {error && (
              <span className="animate-fade-in border border-rose-300/35 bg-rose-400/10 px-3 py-2 text-sm font-medium text-rose-100">
                {error}
              </span>
            )}
          </div>

          <div className="flex justify-center lg:hidden">
            <HeroArt size={220} />
          </div>

          <div className="grid max-w-xl grid-cols-2 gap-x-3 gap-y-4 pt-1 sm:grid-cols-2 sm:pt-2 xl:grid-cols-4">
            {STEPS.map((s) => (
              <div key={s.label} className="group relative min-h-16 sm:min-h-28">
                <div className="flex cursor-help items-center gap-2 border-b border-white/15 pb-3 transition-colors group-hover:border-lime-300/70">
                  <s.icon className="size-4 text-lime-300" />
                  <span className="font-mono text-sm uppercase text-white">{s.label}</span>
                </div>
                <div
                  role="tooltip"
                  className={`pointer-events-none absolute top-10 z-20 hidden w-72 max-w-[calc(100vw-3rem)] translate-y-1 text-left text-xs leading-5 text-white/60 opacity-0 transition-all duration-150 group-hover:translate-y-0 group-hover:opacity-100 sm:block ${s.tooltipClass}`}
                >
                  {s.desc}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="animate-fade-in-up pointer-events-auto absolute right-[-7rem] top-1/2 z-0 hidden w-[62vw] max-w-[820px] -translate-y-1/2 opacity-95 lg:block xl:right-[-4rem]">
          <HeroArt size={820} />
        </div>
      </section>

      <section className="mx-auto w-full max-w-7xl px-6 pb-12 sm:px-8">
        <div className="animate-fade-in-up border-t border-white/12 pt-7">
          <div className="mb-5 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-white">
              <History className="size-5 text-lime-300" /> Past sweeps
            </h2>
            <p className="text-sm text-white/48">Resume a run or review its activity.</p>
          </div>

          {runs.length === 0 ? (
            <div className="flex flex-col items-center gap-2 border border-dashed border-white/16 py-8 text-center">
              <DropInImage
                src="/illustrations/empty-state.png"
                alt="No sweeps yet"
                size={120}
                className="animate-bob opacity-90"
                fallback={<Radar className="size-10 text-lime-300" />}
              />
              <p className="text-sm text-white/56">
                No sweeps yet — hit <span className="font-semibold">Start a new sweep</span> to launch Senty.
              </p>
            </div>
          ) : (
            <ul className="space-y-1.5">
              {runs.map((r) => (
                <li key={r.run_id}>
                  <Link
                    href={`/runs/${r.run_id}`}
                    className="group flex items-center justify-between border-b border-white/10 px-1 py-3 transition-colors hover:border-lime-300/40 hover:bg-white/[0.03]"
                  >
                    <div className="flex items-center gap-3">
                      <span
                        className={`size-2.5 rounded-full ${
                          LAST_EVENT_DOT[r.last_event_type ?? ""] ?? "bg-lime-300"
                        }`}
                      />
                      <span className="font-mono text-sm font-medium text-white group-hover:text-lime-300">
                        {r.run_id}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-white/50">
                      <span className="hidden sm:inline">{formatWhen(r.started_at)}</span>
                      <span>{r.event_count} events</span>
                      {r.last_event_type && (
                        <Badge className="border border-white/10 bg-white/5 font-normal text-white/68 hover:bg-white/5">
                          {r.last_event_type}
                        </Badge>
                      )}
                      <ArrowRight className="size-4 opacity-0 transition-opacity group-hover:opacity-100" />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}
