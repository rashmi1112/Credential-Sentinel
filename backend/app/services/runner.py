"""Drives the graph one segment at a time (start -> next gate, or resume -> next).

The server holds no running graph between requests: every call resumes from the
SQLite checkpoint keyed by ``thread_id == run_id`` (ADR-12). Granular progress
events are emitted by the nodes themselves; here we only emit the gate-reached
and run-completed boundary events after a segment settles.
"""
from __future__ import annotations

from typing import Any, Optional

from .events import broker


def extract_interrupt(snap) -> Optional[dict[str, Any]]:
    """Pull the pending interrupt payload from a state snapshot, across langgraph
    versions (newer expose ``snap.interrupts``; 0.2.x only on tasks)."""
    intr = getattr(snap, "interrupts", None)
    if intr:
        return intr[0].value
    for task in getattr(snap, "tasks", ()) or ():
        task_intr = getattr(task, "interrupts", None)
        if task_intr:
            return task_intr[0].value
    return None


async def run_segment(graph, run_id: str, command: Any = None) -> None:
    cfg = {"configurable": {"thread_id": run_id}}
    inp = command if command is not None else {"run_id": run_id, "status": "running"}
    try:
        async for _chunk in graph.astream(inp, cfg, stream_mode="updates"):
            # Nodes publish their own granular events; nothing to do per chunk.
            pass
        snap = await graph.aget_state(cfg)
        payload = extract_interrupt(snap)
        if snap.next and payload is not None:
            await broker.publish(
                run_id,
                {"type": "gate_reached", "gate": payload.get("gate"), "payload": payload},
            )
        else:
            await broker.publish(run_id, {"type": "run_completed"})
    except Exception as exc:  # surface failures to the live stream
        await broker.publish(run_id, {"type": "error", "message": str(exc)})
