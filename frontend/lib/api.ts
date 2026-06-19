// Typed fetchers to the FastAPI backend.
import type { Decision, GateName, RunListItem, RunSnapshot } from "./types";

export const API =
  process.env.NEXT_PUBLIC_API ?? "http://localhost:8000";

export async function createRun(): Promise<{ run_id: string }> {
  const res = await fetch(`${API}/api/runs`, { method: "POST" });
  if (!res.ok) throw new Error(`createRun failed: ${res.status}`);
  return res.json();
}

export async function listRuns(): Promise<RunListItem[]> {
  const res = await fetch(`${API}/api/runs`, { cache: "no-store" });
  if (!res.ok) throw new Error(`listRuns failed: ${res.status}`);
  return res.json();
}

export async function getRun(runId: string): Promise<RunSnapshot> {
  const res = await fetch(`${API}/api/runs/${runId}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`getRun failed: ${res.status}`);
  return res.json();
}

export async function submitDecisions(
  runId: string,
  gate: GateName,
  decisions: Decision[],
): Promise<void> {
  const res = await fetch(`${API}/api/runs/${runId}/decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ gate, decisions }),
  });
  if (!res.ok && res.status !== 202) {
    throw new Error(`submitDecisions failed: ${res.status}`);
  }
}
