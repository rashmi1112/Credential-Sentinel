"""Local baseline runner for Credential Sentinel (Week 4).

Drives every golden case through the real graph, scores it with the evaluators, then
aggregates per-metric scores, the weighted composite, the ship-gate, and latency.
Writes a results JSON + a submission spreadsheet (CSV).

Passes:
  - sim cases (sim_single_run + two_run)  -> in-process, SENTINEL_TLS_MODE=sim
  - real_tls cases                        -> spawned subprocess with SENTINEL_TLS_MODE=real
                                             (skipped gracefully if the network is unavailable)

Usage:
  python run_baseline.py                 # full 50-case baseline -> results/baseline.{json,csv}
  python run_baseline.py --no-llm        # skip the LLM-judge evaluators (faster/cheaper)
  python run_baseline.py --tag post      # label the run (e.g., post-improvement)
  python run_baseline.py --subset real_tls --out /tmp/x.json   # (internal) real-TLS subprocess
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("SENTINEL_EVAL_MODE", "1")

import harness as H  # noqa: E402  (loads backend/.env, sets sim TLS default)
import evaluators as E  # noqa: E402
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver  # noqa: E402
from app.core import config  # noqa: E402
from app.graph.build import build_graph  # noqa: E402
from app.services import memory  # noqa: E402
from app.services.events import broker  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# Metric category -> (weight, evaluator keys pooled into it)
CATEGORIES = {
    "Safety":         (0.35, ["safety_invariants"]),
    "Routing":        (0.25, ["routing_match"]),
    "Faithfulness":   (0.15, ["plan_faithfulness", "delayed_revoke_present",
                              "injection_resistance", "report_counts_match"]),
    "Prioritization": (0.15, ["urgency_band_match"]),
    "Cost/Latency":   (0.10, ["latency_under_bar"]),  # synthesized below
}
LATENCY_BAR_S = 30.0


async def _reset_stores() -> None:
    broker.configure(tempfile.mktemp(suffix="_e.db"))
    memory.configure(tempfile.mktemp(suffix="_m.db"))
    await broker.init_db()
    await memory.init_db()


async def run_subset(cases: list[dict], use_llm: bool) -> list[dict]:
    results = []
    async with AsyncSqliteSaver.from_conn_string(tempfile.mktemp(suffix=".db")) as saver:
        graph = build_graph(saver)
        for i, case in enumerate(cases):
            await _reset_stores()  # isolate cross-run memory per case
            try:
                if case["requires"] == "two_run":
                    await H.run_case(graph, f"b{i}r1", case)   # seed cycle 1
                    obs = await H.run_case(graph, f"b{i}r2", case)  # cycle 2 diffs vs 1
                else:
                    obs = await H.run_case(graph, f"b{i}", case)
                scores = E.score_case(obs, case, use_llm=use_llm)
                # two_run: add the drift "stuck across cycles" check.
                if "drift_stuck" in case.get("checks", []):
                    stuck = [s["cred_id"] for s in (obs.get("drift") or {}).get("stuck", [])]
                    hit = obs["cred_id"] in stuck
                    scores.append({"key": "drift_stuck", "score": 1.0 if hit else 0.0,
                                   "comment": f"stuck={stuck}"})
            except Exception as exc:
                obs = {"case_id": case["case_id"], "error": str(exc), "latency_s": None}
                scores = [{"key": "run_error", "score": 0.0, "comment": str(exc)}]
            results.append({"case": case, "observed": obs, "scores": scores})
            mark = "ok" if all(s["score"] >= 1.0 for s in scores) else "!!"
            print(f"  [{mark}] {case['case_id']:14} "
                  + " ".join(f"{s['key']}={s['score']:.2f}" for s in scores))
    return results


def aggregate(results: list[dict]) -> dict:
    # Pool individual evaluator scores by key.
    by_key: dict[str, list[float]] = {}
    for r in results:
        for s in r["scores"]:
            by_key.setdefault(s["key"], []).append(s["score"])

    # Synthesize latency_under_bar from observed latencies.
    lats = [r["observed"]["latency_s"] for r in results
            if r["observed"].get("latency_s") is not None]
    if lats:
        by_key["latency_under_bar"] = [1.0 if x <= LATENCY_BAR_S else 0.0 for x in lats]

    per_key = {k: round(statistics.mean(v), 4) for k, v in by_key.items()}

    categories = {}
    composite = 0.0
    for cat, (w, keys) in CATEGORIES.items():
        pool = [x for k in keys for x in by_key.get(k, [])]
        score = round(statistics.mean(pool), 4) if pool else None
        categories[cat] = {"weight": w, "score": score, "n": len(pool)}
        if score is not None:
            composite += w * score

    # Ship gate: safety perfect AND no missed at-risk credential / no false-DEFER.
    safety_ok = all(s["score"] >= 1.0 for r in results for s in r["scores"]
                    if s["key"] == "safety_invariants")
    at_risk = [r for r in results
               if r["case"]["expected"]["routing"] in ("OWN_UNMANAGED", "OWN_STALE")]
    at_risk_hits = sum(1 for r in at_risk
                       if r["observed"].get("routing") == r["case"]["expected"]["routing"])
    at_risk_recall = round(at_risk_hits / len(at_risk), 4) if at_risk else None
    false_defer = [r["case"]["case_id"] for r in at_risk
                   if r["observed"].get("routing") == "DEFER"]

    return {
        "composite": round(composite, 4),
        "categories": categories,
        "per_evaluator": per_key,
        "ship_gate": {
            "safety_100": safety_ok,
            "at_risk_recall": at_risk_recall,
            "false_defer_cases": false_defer,
            "passes": bool(safety_ok and at_risk_recall == 1.0 and not false_defer),
        },
        "latency": {
            "p50": round(statistics.median(lats), 3) if lats else None,
            "p95": round(sorted(lats)[int(0.95 * (len(lats) - 1))], 3) if lats else None,
            "max": round(max(lats), 3) if lats else None,
            "bar_s": LATENCY_BAR_S,
        },
        "n_cases": len(results),
    }


def failure_category(scores: list[dict]) -> str:
    cats = []
    for s in scores:
        if s["score"] >= 1.0:
            continue
        for cat, (_, keys) in CATEGORIES.items():
            if s["key"] in keys:
                cats.append(cat)
        if s["key"] in ("drift_stuck", "run_error"):
            cats.append("Other")
    return ",".join(sorted(set(cats))) or "none"


def write_outputs(results: list[dict], agg: dict, tag: str) -> None:
    RESULTS_DIR.mkdir(exist_ok=True)
    base = RESULTS_DIR / tag
    (base.with_suffix(".json")).write_text(json.dumps(
        {"tag": tag, "aggregate": agg, "results": results}, indent=2, default=str))

    # Submission spreadsheet: ground truth vs predicted, per-metric, PASS/FAIL, category.
    eval_keys = ["routing_match", "urgency_band_match", "safety_invariants",
                 "report_counts_match", "delayed_revoke_present",
                 "plan_faithfulness", "injection_resistance", "drift_stuck"]
    with (base.with_suffix(".csv")).open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "scenario", "difficulty",
                    "exp_routing", "obs_routing", "exp_band", "obs_band",
                    "exp_disposition", "obs_disposition", "plan_source",
                    *eval_keys, "PASS_FAIL", "failure_category", "latency_s"])
        for r in results:
            c, o, sc = r["case"], r["observed"], {s["key"]: s["score"] for s in r["scores"]}
            passed = all(v >= 1.0 for v in sc.values())
            w.writerow([
                c["case_id"], c["scenario_type"], c["difficulty"],
                c["expected"]["routing"], o.get("routing"),
                c["expected"].get("urgency_band"), o.get("urgency_band"),
                c["expected"]["disposition"], o.get("disposition"), o.get("plan_source"),
                *[("" if k not in sc else round(sc[k], 2)) for k in eval_keys],
                "PASS" if passed else "FAIL", failure_category(r["scores"]),
                o.get("latency_s"),
            ])
    print(f"\nWrote {base.with_suffix('.json').name} and {base.with_suffix('.csv').name} "
          f"-> {RESULTS_DIR}")


def print_summary(agg: dict) -> None:
    print("\n" + "=" * 60)
    print(f"COMPOSITE: {agg['composite']:.3f}   (n={agg['n_cases']})")
    print("-" * 60)
    for cat, d in agg["categories"].items():
        s = "n/a" if d["score"] is None else f"{d['score']:.3f}"
        print(f"  {cat:16} {s:>7}   (w={d['weight']}, n={d['n']})")
    print("-" * 60)
    g = agg["ship_gate"]
    print(f"  SHIP GATE: {'PASS' if g['passes'] else 'FAIL'}  "
          f"(safety_100={g['safety_100']}, at_risk_recall={g['at_risk_recall']}, "
          f"false_defer={g['false_defer_cases']})")
    L = agg["latency"]
    print(f"  Latency: p50={L['p50']}s p95={L['p95']}s max={L['max']}s (bar {L['bar_s']}s)")
    print("=" * 60)


async def amain() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--tag", default="baseline")
    ap.add_argument("--subset", choices=["sim", "real_tls", "all"], default="all")
    ap.add_argument("--out", default=None, help="internal: dump raw results JSON to this path")
    args = ap.parse_args()
    use_llm = not args.no_llm

    cases = H.CASES
    sim_cases = [c for c in cases if c["requires"] in ("sim_single_run", "two_run")]
    real_cases = [c for c in cases if c["requires"] == "real_tls"]

    if args.subset == "real_tls":
        print(f"[real-tls subprocess] {len(real_cases)} case(s), TLS_MODE={config.TLS_MODE}")
        res = await run_subset(real_cases, use_llm)
        Path(args.out).write_text(json.dumps(res, default=str))
        return

    print(f"Running sim pass: {len(sim_cases)} cases (TLS_MODE={config.TLS_MODE}, "
          f"EVAL_MODE={config.EVAL_MODE}, LLM judge={'on' if use_llm else 'off'})")
    results = await run_subset(sim_cases, use_llm)

    if args.subset == "all" and real_cases:
        print(f"\nSpawning real-TLS subprocess for {len(real_cases)} case(s)…")
        tmp = tempfile.mktemp(suffix="_realtls.json")
        env = {**os.environ, "SENTINEL_TLS_MODE": "real"}
        cmd = [sys.executable, __file__, "--subset", "real_tls", "--out", tmp,
               *(["--no-llm"] if args.no_llm else [])]
        try:
            subprocess.run(cmd, env=env, check=True, timeout=180)
            results += json.loads(Path(tmp).read_text())
        except Exception as exc:
            print(f"  real-TLS pass skipped ({exc}); marking {len(real_cases)} cases as skipped")
            for c in real_cases:
                results.append({"case": c, "observed": {"case_id": c["case_id"], "latency_s": None,
                               "error": "real-tls pass unavailable"},
                               "scores": [{"key": "run_error", "score": 0.0,
                                           "comment": "real-tls pass unavailable"}]})

    agg = aggregate(results)
    write_outputs(results, agg, args.tag)
    print_summary(agg)


if __name__ == "__main__":
    asyncio.run(amain())
