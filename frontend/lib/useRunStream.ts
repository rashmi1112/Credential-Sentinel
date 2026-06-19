"use client";

import { useEffect, useRef, useState } from "react";
import { API } from "./api";
import type { GatePayload, Routing, RunEvent } from "./types";

export interface RunStreamState {
  events: RunEvent[];
  reconciliation: { cred_id: string; label: string; routing: Routing }[];
  gate: GatePayload | null;
  done: boolean;
  error: string | null;
}

/**
 * Subscribes to a run's SSE stream. The backend replays its persisted log on
 * connect, so this hook always reflects the full history even after a reload or
 * reconnect. Everything is keyed to runId; the seq field dedups replays.
 */
export function useRunStream(runId: string | null): RunStreamState {
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [reconciliation, setReconciliation] = useState<
    { cred_id: string; label: string; routing: Routing }[]
  >([]);
  const [gate, setGate] = useState<GatePayload | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seenSeq = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!runId) return;
    // Reset for a new run.
    setEvents([]);
    setReconciliation([]);
    setGate(null);
    setDone(false);
    setError(null);
    seenSeq.current = new Set();

    const es = new EventSource(`${API}/api/runs/${runId}/events`);

    es.onmessage = (e) => {
      const ev = JSON.parse(e.data) as RunEvent;
      if (ev.seq !== undefined) {
        if (seenSeq.current.has(ev.seq)) return;
        seenSeq.current.add(ev.seq);
      }
      setEvents((prev) => [...prev, ev]);

      switch (ev.type) {
        case "reconciliation_item":
          setReconciliation((prev) => {
            const next = prev.filter((r) => r.cred_id !== ev.cred_id);
            return [
              ...next,
              {
                cred_id: ev.cred_id!,
                label: ev.label ?? ev.cred_id!,
                routing: (ev.routing ?? "UNKNOWN") as Routing,
              },
            ];
          });
          break;
        case "gate_reached":
          setGate(ev.payload ?? null);
          break;
        case "run_completed":
          setDone(true);
          es.close();
          break;
        case "error":
          setError(ev.message ?? "unknown error");
          break;
      }
    };

    es.onerror = () => {
      // Browser auto-reconnects; backend replays. Close only when done.
      if (done) es.close();
    };

    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  return { events, reconciliation, gate, done, error };
}
