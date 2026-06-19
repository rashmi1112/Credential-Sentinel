"""Run endpoints: create, stream (SSE), decide, snapshot, list, audit."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from langgraph.types import Command
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..services.events import broker
from ..services.runner import extract_interrupt, run_segment

router = APIRouter(prefix="/api", tags=["runs"])

# Keep references to background tasks so they aren't garbage-collected mid-run.
_bg_tasks: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


class Decision(BaseModel):
    cred_id: str
    action: Literal["approve", "reject", "edit"]
    edits: Optional[dict[str, Any]] = None


class DecisionsBody(BaseModel):
    gate: Literal["staging", "cutover"]
    decisions: list[Decision]


@router.post("/runs")
async def create_run(request: Request) -> dict[str, str]:
    run_id = uuid.uuid4().hex[:12]
    graph = request.app.state.graph
    _spawn(run_segment(graph, run_id))
    return {"run_id": run_id}


@router.get("/runs")
async def list_runs() -> list[dict[str, Any]]:
    return await broker.list_runs()


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> dict[str, Any]:
    graph = request.app.state.graph
    cfg = {"configurable": {"thread_id": run_id}}
    snap = await graph.aget_state(cfg)
    values = snap.values or {}
    pending_gate = extract_interrupt(snap)
    return {
        "run_id": run_id,
        "status": values.get("status", "unknown"),
        "live_inventory": values.get("live_inventory", []),
        "managed_inventory": values.get("managed_inventory", []),
        "reconciliation": values.get("reconciliation", {}),
        "queue": values.get("queue", []),
        "staging_results": values.get("staging_results", {}),
        "pending_gate": pending_gate,
        "next": list(snap.next) if snap.next else [],
    }


@router.get("/runs/{run_id}/audit")
async def get_audit(run_id: str, request: Request) -> dict[str, Any]:
    graph = request.app.state.graph
    cfg = {"configurable": {"thread_id": run_id}}
    snap = await graph.aget_state(cfg)
    values = snap.values or {}
    # Phase 0: surface the persisted event log as a stand-in audit trail.
    return {"run_id": run_id, "audit_log": values.get("audit_log", []), "events": await broker.replay(run_id)}


@router.post("/runs/{run_id}/decisions", status_code=202)
async def submit_decisions(run_id: str, body: DecisionsBody, request: Request) -> JSONResponse:
    graph = request.app.state.graph
    resume = {"gate": body.gate, "decisions": [d.model_dump() for d in body.decisions]}
    _spawn(run_segment(graph, run_id, Command(resume=resume)))
    return JSONResponse({"status": "resuming"}, status_code=202)


@router.get("/runs/{run_id}/events")
async def stream_events(run_id: str, request: Request) -> EventSourceResponse:
    async def generator():
        # Subscribe first, then replay, so nothing published in between is lost;
        # dedup by per-run seq.
        q = broker.subscribe(run_id)
        seen: set[int] = set()
        try:
            for ev in await broker.replay(run_id):
                if ev.get("seq") is not None:
                    seen.add(ev["seq"])
                yield {"data": json.dumps(ev)}
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield {"comment": "keepalive"}
                    continue
                if ev.get("seq") in seen:
                    continue
                yield {"data": json.dumps(ev)}
        finally:
            broker.unsubscribe(run_id, q)

    return EventSourceResponse(generator())
