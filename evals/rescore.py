"""Re-score a stored results file against the current golden dataset.

Used when an evaluator or a golden label changes: we recompute the *code* evaluators
(which depend on labels) from the stored observations, and keep the stored *LLM-judge*
scores (which depend only on the agent's output, not the label) plus drift/run_error.
This lets baseline / imp1 / imp2 all be scored on one consistent dataset version
without re-running the graph or paying for the judge again.

Usage:  python rescore.py baseline imp1 [imp2 ...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import evaluators as E
import run_baseline as RB

CASES = json.loads((Path(__file__).resolve().parent / "golden" / "cases.json").read_text())["cases"]
CASE_BY_ID = {c["case_id"]: c for c in CASES}

# Scores preserved as-is (do not depend on the golden label).
KEEP = {"plan_faithfulness", "injection_resistance", "drift_stuck", "run_error"}


def rescore(tag: str) -> None:
    path = RB.RESULTS_DIR / f"{tag}.json"
    data = json.loads(path.read_text())
    for r in data["results"]:
        case = CASE_BY_ID[r["case"]["case_id"]]
        r["case"] = case  # refresh to corrected labels
        kept = [s for s in r["scores"] if s["key"] in KEEP]
        recomputed = []
        for ev in E.CODE_EVALUATORS:
            out = ev(r["observed"], case)
            if out is not None:
                recomputed.append(out)
        r["scores"] = recomputed + kept
    agg = RB.aggregate(data["results"])
    RB.write_outputs(data["results"], agg, tag)
    print(f"\n### rescored: {tag}")
    RB.print_summary(agg)


if __name__ == "__main__":
    for t in sys.argv[1:] or ["baseline"]:
        rescore(t)
