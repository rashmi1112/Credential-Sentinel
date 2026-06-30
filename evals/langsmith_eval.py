"""LangSmith driver for the Credential Sentinel eval.

Reuses the same harness (target) and evaluators as the local runner, so the LangSmith
numbers match. Tracing is on, so every graph node + the Nebius LLM calls (tokens,
latency) show up under the project.

Subcommands:
  upload     create/refresh the 'credential-sentinel-eval' dataset (all 50 cases)
  smoke      run ONE case through the traced graph -> confirm the trace in the UI
  evaluate [tag]   run client.aevaluate over the sim-compatible cases, recording an
                   experiment with per-metric scores (default tag: imp2b)

Env: forces LANGCHAIN_TRACING_V2=true and project before importing the app so the
Nebius client gets wrapped for tracing.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import uuid
from pathlib import Path

os.environ.setdefault("SENTINEL_EVAL_MODE", "1")
os.environ.setdefault("SENTINEL_TLS_MODE", "sim")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ.setdefault("LANGCHAIN_PROJECT", "credential-sentinel-eval")

import harness as H  # noqa: E402 (loads backend/.env: NEBIUS/LANGCHAIN/OPENAI keys)
import evaluators as E  # noqa: E402
from langsmith import Client, aevaluate  # noqa: E402
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver  # noqa: E402
from app.graph.build import build_graph  # noqa: E402
from app.services import memory  # noqa: E402
from app.services.events import broker  # noqa: E402

DATASET = "credential-sentinel-eval"
PROJECT = os.environ["LANGCHAIN_PROJECT"]
CASE_BY_ID = {c["case_id"]: c for c in H.CASES}


def upload() -> None:
    client = Client()
    try:
        ds = client.read_dataset(dataset_name=DATASET)
        print(f"dataset exists: {DATASET} ({ds.id})")
    except Exception:
        ds = client.create_dataset(DATASET, description="Credential Sentinel golden dataset, 50 cases (v-final)")
        print(f"created dataset: {DATASET} ({ds.id})")
    existing = list(client.list_examples(dataset_id=ds.id))
    if existing:
        print(f"  already has {len(existing)} examples; leaving as-is "
              f"(delete in the UI to re-upload).")
        return
    client.create_examples(
        dataset_id=ds.id,
        inputs=[{"case_id": c["case_id"], **c["input"], "requires": c["requires"],
                 "scenario_type": c["scenario_type"], "checks": c["checks"]} for c in H.CASES],
        outputs=[c["expected"] for c in H.CASES],
        metadata=[{"scenario": c["scenario_type"], "difficulty": c["difficulty"],
                   "requires": c["requires"]} for c in H.CASES],
    )
    print(f"  uploaded {len(H.CASES)} examples")


async def _run_one(graph, case: dict) -> dict:
    rid = "ls-" + uuid.uuid4().hex[:8]
    if case["requires"] == "two_run":
        await H.run_case(graph, rid + "r1", case)
        return await H.run_case(graph, rid + "r2", case)
    return await H.run_case(graph, rid, case)


async def _fresh_graph_run(case: dict) -> dict:
    broker.configure(tempfile.mktemp(suffix="_e.db"))
    memory.configure(tempfile.mktemp(suffix="_m.db"))
    await broker.init_db()
    await memory.init_db()
    async with AsyncSqliteSaver.from_conn_string(tempfile.mktemp(suffix=".db")) as saver:
        return await _run_one(build_graph(saver), case)


async def smoke() -> None:
    case = CASE_BY_ID["happy-01"]
    print(f"Running {case['case_id']} through the traced graph (project={PROJECT})…")
    obs = await _fresh_graph_run(case)
    print(f"  routing={obs['routing']} disposition={obs['disposition']} "
          f"plan_source={obs['plan_source']} latency={obs['latency_s']}s")
    print("\nOpen https://smith.langchain.com  ->  project '" + PROJECT + "'.")
    print("Confirm the trace shows: top-level run, every node (discover…report), "
          "the Nebius LLM call(s) with token counts, and latency per step.")


def all_metrics(run, example):
    """One LangSmith evaluator returning all per-case metric results."""
    observed = run.outputs or {}
    case = CASE_BY_ID[example.inputs["case_id"]]
    results = E.score_case(observed, case, use_llm=True)
    if "drift_stuck" in case.get("checks", []):
        stuck = [s["cred_id"] for s in (observed.get("drift") or {}).get("stuck", [])]
        results.append({"key": "drift_stuck", "comment": f"stuck={stuck}",
                        "score": 1.0 if observed.get("cred_id") in stuck else 0.0})
    return {"results": [{"key": r["key"], "score": r["score"], "comment": r["comment"]}
                        for r in results]}


async def _target(inputs: dict) -> dict:
    """LangSmith target: must be a real coroutine function (not a lambda) so aevaluate
    detects it as the target rather than an experiment to resume."""
    return await _fresh_graph_run(CASE_BY_ID[inputs["case_id"]])


async def evaluate(tag: str) -> None:
    client = Client()
    # Sim-compatible cases only (real-TLS cases need live network; validated locally).
    examples = [e for e in client.list_examples(dataset_name=DATASET)
                if (e.metadata or {}).get("requires") != "real_tls"]
    print(f"aevaluate '{tag}' over {len(examples)} cases (project={PROJECT})…")
    res = await aevaluate(
        _target,
        data=examples,
        evaluators=[all_metrics],
        experiment_prefix=tag,
        max_concurrency=1,  # broker/memory are process-global; serialize
        client=client,
    )
    print("experiment:", getattr(res, "experiment_name", tag))


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    if cmd == "upload":
        upload()
    elif cmd == "smoke":
        asyncio.run(smoke())
    elif cmd == "evaluate":
        asyncio.run(evaluate(sys.argv[2] if len(sys.argv) > 2 else "imp2b"))
    else:
        print(f"unknown command: {cmd}")


if __name__ == "__main__":
    main()
