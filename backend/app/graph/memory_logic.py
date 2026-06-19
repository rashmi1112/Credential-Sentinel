"""Pure functions for run dispositions and cross-run coverage drift (Feature B).

No I/O — easy to test and reason about. A credential is "resolved" if it was
safely handled this cycle (cut over, or deferred to its service of record);
anything else is still at risk and counts as unresolved.
"""
from __future__ import annotations

from typing import Any

RESOLVED = {"cut_over", "deferred"}


def disposition(cid: str, state: dict[str, Any]) -> str:
    """How did this credential end the run?"""
    routing = state.get("reconciliation", {}).get(cid)
    if routing == "DEFER":
        return "deferred"
    if routing == "UNKNOWN":
        return "escalated"

    cutover = state.get("cutover_results", {}).get(cid)
    if cutover:
        return "cut_over" if cutover.get("status") == "cutover_complete" else "rolled_back"

    staging = state.get("staging_results", {}).get(cid)
    if staging:
        return "staged" if staging.get("status") == "staged_healthy" else "escalated"

    assessment = state.get("assessments", {}).get(cid, {}).get("assessment")
    if assessment and not assessment.get("safe_to_rotate", True):
        return "escalated"  # blocked at assess (e.g., consumers not enumerable)
    if assessment:
        return "rejected"  # owned + assessable but never staged → rejected at Gate 1
    return "pending"


def build_summary(state: dict[str, Any]) -> dict[str, Any]:
    labels = {c["id"]: c.get("label", c["id"]) for c in state.get("live_inventory", [])}
    routing = state.get("reconciliation", {})
    creds = {
        cid: {
            "routing": routing.get(cid),
            "disposition": disposition(cid, state),
            "label": labels.get(cid, cid),
        }
        for cid in routing
    }
    return {"creds": creds}


def compute_drift(prior: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    """Diff the current run's summary against the prior run's."""
    cur = current.get("creds", {})
    if not prior:
        return {"prior_run_id": None, "new": [], "changed": [], "stuck": [], "first_run": True}

    prev = prior.get("creds", {})
    owned = {"OWN_UNMANAGED", "OWN_STALE"}

    new = [
        {"cred_id": cid, "label": c["label"], "routing": c["routing"]}
        for cid, c in cur.items()
        if cid not in prev and c["routing"] in owned
    ]
    changed = [
        {"cred_id": cid, "label": c["label"], "from": prev[cid]["routing"], "to": c["routing"]}
        for cid, c in cur.items()
        if cid in prev and prev[cid]["routing"] != c["routing"]
    ]
    stuck = [
        {"cred_id": cid, "label": c["label"], "disposition": c["disposition"]}
        for cid, c in cur.items()
        if cid in prev
        and prev[cid]["disposition"] not in RESOLVED
        and c["disposition"] not in RESOLVED
    ]
    return {
        "prior_run_id": prior.get("run_id"),
        "new": new,
        "changed": changed,
        "stuck": stuck,
        "first_run": False,
    }
