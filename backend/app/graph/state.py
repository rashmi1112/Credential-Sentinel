"""The shared LangGraph state for a Sentinel run.

In Phase 0 the inner shapes are plain dicts; later phases replace them with the
dataclasses described in section 6 of the plan. ``total=False`` lets nodes
return partial updates.
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class SentinelState(TypedDict, total=False):
    run_id: str
    config: dict[str, Any]
    # Optional injected inventories (Week 4 eval). When present, discover/
    # list_managed use these instead of the simulated globals, so a golden-dataset
    # case can drive its own credentials through the real graph. Absent in normal
    # runs → falls back to simdata (demo + smoke test unchanged).
    live_seed: list[dict[str, Any]]
    managed_seed: list[dict[str, Any]]
    live_inventory: list[dict[str, Any]]
    managed_inventory: list[dict[str, Any]]
    reconciliation: dict[str, str]  # cred_id -> DEFER | OWN_UNMANAGED | OWN_STALE | UNKNOWN
    assessments: dict[str, Any]     # cred_id -> {assessment, urgency}
    plans: dict[str, Any]           # cred_id -> drafted rotation plan
    queue: list[str]
    staging_results: dict[str, Any]
    cutover_results: dict[str, Any]  # cred_id -> {status: cutover_complete | rolled_back}
    pending_approvals: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    audit_log: list[dict[str, Any]]
    drift: dict[str, Any]            # cross-run coverage drift (Feature B)
    run_report: dict[str, Any]       # end-of-run narrative (Nebius)
    prior_run_id: Optional[str]
    status: str
    # Captured resume payloads from the two interrupt gates.
    staging_decisions: Any
    cutover_decisions: Any
