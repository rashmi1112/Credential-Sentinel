"""Run ONE golden case through the real Credential Sentinel graph, headless.

Injects the case's inventory via ``live_seed`` / ``managed_seed`` (Week-4 refactor),
auto-approves both gates (like smoke_test.py), and returns the observed decisions so
evaluators can score them. Forces SENTINEL_EVAL_MODE so latency reflects real compute.

Usage (smoke):  python harness.py            # runs 3 sample cases, prints observed vs expected
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("SENTINEL_EVAL_MODE", "1")
os.environ.setdefault("SENTINEL_TLS_MODE", "sim")  # default: offline/deterministic

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

# Load the backend .env explicitly by path (NEBIUS / LANGCHAIN / OPENAI keys) so the
# eval works regardless of the current working directory, before app config imports.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND / ".env")

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver  # noqa: E402
from langgraph.types import Command  # noqa: E402

from app.graph.build import build_graph  # noqa: E402
from app.graph.memory_logic import disposition  # noqa: E402
from app.services import memory  # noqa: E402
from app.services.events import broker  # noqa: E402
from app.services.runner import extract_interrupt  # noqa: E402

CASES = json.loads((Path(__file__).resolve().parent / "golden" / "cases.json").read_text())["cases"]


async def run_case(graph, run_id: str, case: dict) -> dict:
    """Drive one full sweep with the case's injected inventory; approve every gate."""
    cfg = {"configurable": {"thread_id": run_id}}

    async def drive(inp):
        async for _ in graph.astream(inp, cfg, stream_mode="updates"):
            pass
        return await graph.aget_state(cfg)

    t0 = time.perf_counter()
    init = {
        "run_id": run_id,
        "status": "running",
        "live_seed": case["input"]["live"],
        "managed_seed": case["input"]["managed"],
    }
    snap = await drive(init)
    g1 = extract_interrupt(snap)
    if g1 and g1.get("gate") == "staging":
        snap = await drive(Command(resume={"gate": "staging", "decisions": [
            {"cred_id": i["cred_id"], "action": "approve"} for i in g1["items"]
        ]}))
        g2 = extract_interrupt(snap)
        if g2 and g2.get("gate") == "cutover":
            snap = await drive(Command(resume={"gate": "cutover", "decisions": [
                {"cred_id": i["cred_id"], "action": "approve"} for i in g2["items"]
            ]}))
    elapsed = time.perf_counter() - t0

    st = snap.values
    cid = case["input"]["live"][0]["id"]
    routing = st.get("reconciliation", {}).get(cid)
    assessment = st.get("assessments", {}).get(cid, {})
    urgency = assessment.get("urgency", {})
    plan = st.get("plans", {}).get(cid)
    events = await broker.replay(run_id)
    return {
        "case_id": case["case_id"],
        "cred_id": cid,
        "input_cred": case["input"]["live"][0],
        "routing": routing,
        "safe_to_rotate": assessment.get("assessment", {}).get("safe_to_rotate"),
        "blocked_reason": assessment.get("assessment", {}).get("blocked_reason"),
        "urgency_band": urgency.get("band"),
        "urgency_score": urgency.get("score"),
        "disposition": disposition(cid, dict(st)),
        "in_staging_results": cid in st.get("staging_results", {}),
        "staging_status": st.get("staging_results", {}).get(cid, {}).get("status"),
        "in_cutover_results": cid in st.get("cutover_results", {}),
        "cutover_status": st.get("cutover_results", {}).get(cid, {}).get("status"),
        "in_assessments": cid in st.get("assessments", {}),
        "plan": plan,
        "run_report": st.get("run_report"),
        "counts": (st.get("run_report") or {}).get("counts", {}),
        "cutover_steps": [
            {"step": e.get("step"), "status": e.get("status")}
            for e in events if e.get("type") == "cutover_step" and e.get("cred_id") == cid
        ],
        "plan_source": (plan or {}).get("source"),
        "drift": st.get("drift"),
        "latency_s": round(elapsed, 3),
    }


async def main(sample_ids: list[str] | None = None) -> None:
    broker.configure(tempfile.mktemp(suffix="_events.db"))
    memory.configure(tempfile.mktemp(suffix="_memory.db"))
    await broker.init_db()
    await memory.init_db()

    sample = (
        [c for c in CASES if c["case_id"] in sample_ids] if sample_ids
        else [CASES[0], CASES[25], CASES[40]]  # one happy, one edge, one known-failure
    )

    async with AsyncSqliteSaver.from_conn_string(tempfile.mktemp(suffix=".db")) as saver:
        graph = build_graph(saver)
        for i, case in enumerate(sample):
            if case["requires"] != "sim_single_run":
                print(f"[skip] {case['case_id']} requires {case['requires']}")
                continue
            obs = await run_case(graph, f"eval-{i}", case)
            exp = case["expected"]
            ok = (obs["routing"] == exp["routing"]
                  and obs["disposition"] == exp["disposition"])
            mark = "OK " if ok else "XX "
            print(f"{mark}{case['case_id']:12} routing={obs['routing']}/{exp['routing']} "
                  f"disp={obs['disposition']}/{exp['disposition']} "
                  f"band={obs['urgency_band']}/{exp['urgency_band']} "
                  f"lat={obs['latency_s']}s")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or None))
