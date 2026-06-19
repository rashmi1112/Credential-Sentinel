"""Headless end-to-end test of the graph: run -> gate1 -> resume -> gate2 ->
resume -> complete, all through the same checkpointer. Runs two sweeps to
exercise cross-run coverage drift. Forces the deterministic plan/report fallback
and sim TLS so it's fast and offline regardless of any configured Nebius key."""
import os

os.environ["NEBIUS_API_KEY"] = ""  # before app imports load_dotenv-backed config
os.environ["SENTINEL_TLS_MODE"] = "sim"  # offline: skip the real TLS handshake

import asyncio
import tempfile

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from app.graph.build import build_graph
from app.services import memory
from app.services.events import broker
from app.services.runner import extract_interrupt


async def run_sweep(graph, run_id: str) -> list[dict]:
    """Drive one full sweep, approving every credential at both gates."""
    cfg = {"configurable": {"thread_id": run_id}}

    async def drive(inp):
        async for _ in graph.astream(inp, cfg, stream_mode="updates"):
            pass
        return await graph.aget_state(cfg)

    snap = await drive({"run_id": run_id, "status": "running"})
    g1 = extract_interrupt(snap)
    assert g1 and g1["gate"] == "staging", "expected gate 1 (staging)"
    snap = await drive(Command(resume={"gate": "staging", "decisions": [
        {"cred_id": i["cred_id"], "action": "approve"} for i in g1["items"]
    ]}))
    g2 = extract_interrupt(snap)
    assert g2 and g2["gate"] == "cutover", "expected gate 2 (cutover)"
    snap = await drive(Command(resume={"gate": "cutover", "decisions": [
        {"cred_id": i["cred_id"], "action": "approve"} for i in g2["items"]
    ]}))
    assert not snap.next, f"expected completion, got next={snap.next}"
    assert snap.values["status"] == "completed"
    return await broker.replay(run_id)


async def main():
    db = tempfile.mktemp(suffix=".db")
    broker.configure(tempfile.mktemp(suffix="_events.db"))
    memory.configure(tempfile.mktemp(suffix="_memory.db"))
    await broker.init_db()
    await memory.init_db()

    async with AsyncSqliteSaver.from_conn_string(db) as saver:
        graph = build_graph(saver)

        # Run 1
        ev1 = await run_sweep(graph, "smoke1")
        types = [e["type"] for e in ev1]
        for required in ("reconciliation_item", "staging_result", "cutover_step",
                         "cutover_result", "drift_summary", "report_ready"):
            assert required in types, f"missing event: {required}"
        drift1 = next(e for e in ev1 if e["type"] == "drift_summary")
        print("RUN 1 drift first_run:", drift1["first_run"])
        assert drift1["first_run"] is True

        # Run 2 — diffs against run 1
        ev2 = await run_sweep(graph, "smoke2")
        drift2 = next(e for e in ev2 if e["type"] == "drift_summary")
        report2 = next(e for e in ev2 if e["type"] == "report_ready")
        print("RUN 2 drift prior:", drift2["prior_run_id"],
              "| stuck:", [s["cred_id"] for s in drift2["stuck"]])
        print("RUN 2 report:", report2["headline"])
        assert drift2["first_run"] is False
        assert drift2["prior_run_id"] == "smoke1"
        # api-key-legacy escalates both runs (unhealthy staging) → stuck across cycles.
        assert any(s["cred_id"] == "api-key-legacy" for s in drift2["stuck"]), drift2["stuck"]
        print("SMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
