"""Graph nodes.

Phase 0: discover / list_managed / reconcile / gate / cutover / report are still
simulated (Phase 1 makes discovery + reconciliation real).
Phase 2 (REAL logic): ``assess`` (deterministic), ``prioritize`` (deterministic
urgency), ``plan`` (Nebius Token Factory), and ``stage`` (bounded retry +
staged-but-unhealthy escalation). These operate on the simulated inventory, so
only the *inputs* are simulated — the assessment/scoring/planning/staging is real.
"""
from __future__ import annotations

import asyncio
from typing import Any

from langgraph.types import interrupt

from ..core.config import TLS_MODE
from ..core.nebius import draft_plan, draft_report, nebius_configured
from ..core.policy import load_policy
from ..services import memory
from ..services.events import broker
from . import simdata
from .memory_logic import build_summary, compute_drift
from .scoring import assess_credential, score_urgency
from .state import SentinelState
from .tools.tls import check_tls_expiry


async def _emit(run_id: str, type_: str, **data: Any) -> None:
    await broker.publish(run_id, {"type": type_, **data})


def _labels(state: SentinelState) -> dict[str, str]:
    return {c["id"]: c["label"] for c in state.get("live_inventory", [])}


def _cred_by_id(state: SentinelState, cred_id: str) -> dict[str, Any] | None:
    """Look the credential up in the post-discovery inventory (which carries any
    live-TLS enrichment), not the raw simulated source."""
    for c in state.get("live_inventory", []):
        if c["id"] == cred_id:
            return c
    return None


# --------------------------------------------------------------------------- #
# Phase 0/1 (still simulated)
# --------------------------------------------------------------------------- #
async def discover(state: SentinelState) -> dict[str, Any]:
    run_id = state["run_id"]
    await _emit(run_id, "node_update", node="discover", message="Discovering live credentials…")
    await asyncio.sleep(0.4)
    live: list[dict[str, Any]] = []
    for src in simdata.SIM_LIVE:
        cred = dict(src)
        # The one genuinely live source: a real TLS handshake for cert endpoints.
        if cred.get("kind") == "tls_cert" and cred.get("endpoint") and TLS_MODE == "real":
            ep = cred["endpoint"]
            await _emit(run_id, "node_update", node="discover", message=f"Live TLS handshake → {ep} …")
            res = await check_tls_expiry(ep)
            if res["ok"]:
                cred["not_after"] = res["not_after"]
                cred["not_after_days"] = res["days_to_expiry"]
                cred["expiry_source"] = "real_tls"
                cred["issuer"] = res.get("issuer")
                left = "EXPIRED" if res["expired"] else f"{res['days_to_expiry']}d left"
                await _emit(
                    run_id, "node_update", node="discover",
                    message=f"{ep}: live cert notAfter {res['not_after']} ({left})",
                )
            else:
                # Source unreachable → don't assume safe; flag unknown coverage.
                cred["expiry_source"] = "unknown"
                cred["tls_error"] = res.get("error")
                await _emit(
                    run_id, "node_update", node="discover",
                    message=f"{ep}: TLS check failed ({res.get('error')}) — flagged unknown coverage",
                )
        else:
            cred.setdefault("expiry_source", "simulated")
        live.append(cred)
        await asyncio.sleep(0.1)
    await _emit(
        run_id, "node_update", node="discover",
        message=f"Found {len(live)} live credentials in production",
    )
    return {"live_inventory": live, "status": "discovered"}


async def list_managed(state: SentinelState) -> dict[str, Any]:
    run_id = state["run_id"]
    await _emit(run_id, "node_update", node="list_managed", message="Listing managed inventory…")
    await asyncio.sleep(0.4)
    managed = simdata.SIM_MANAGED
    await _emit(
        run_id, "node_update", node="list_managed",
        message=f"{len(managed)} credential(s) claimed by rotation services",
    )
    return {"managed_inventory": managed, "status": "managed_listed"}


async def reconcile(state: SentinelState) -> dict[str, Any]:
    run_id = state["run_id"]
    await _emit(run_id, "node_update", node="reconcile", message="Reconciling coverage…")
    await asyncio.sleep(0.3)
    managed_ids = {m["id"] for m in state.get("managed_inventory", []) if m.get("rotating")}
    labels = _labels(state)
    # store -> whether it is actively rotating that credential
    managed_rotating = {m["id"] for m in state.get("managed_inventory", []) if m.get("rotating")}
    managed_present = {m["id"] for m in state.get("managed_inventory", [])}
    routing: dict[str, str] = {}
    for cred in state.get("live_inventory", []):
        cid = cred["id"]
        if cred.get("expiry_source") == "unknown":
            routing[cid] = "UNKNOWN"  # couldn't classify → human, never assumed safe (ADR-4)
        elif cid in managed_rotating:
            routing[cid] = "DEFER"  # owned and actively rotating → defer to service of record
        elif cid in managed_present:
            routing[cid] = "OWN_STALE"  # in a store but not rotating → managed-but-unrotating
        else:
            routing[cid] = "OWN_UNMANAGED"  # falls through the cracks → agent owns it
        await _emit(
            run_id, "reconciliation_item",
            cred_id=cid, label=labels.get(cid, cid), routing=routing[cid],
        )
        await asyncio.sleep(0.15)
    return {"reconciliation": routing, "status": "reconciled"}


# --------------------------------------------------------------------------- #
# Phase 2 (real logic)
# --------------------------------------------------------------------------- #
async def assess(state: SentinelState) -> dict[str, Any]:
    run_id = state["run_id"]
    await _emit(run_id, "node_update", node="assess",
                message="Assessing expiry, consumers, and rotation safety…")
    routing = state.get("reconciliation", {})
    # UNKNOWN coverage is escalated, never assessed or assumed safe (ADR-4).
    for cid, r in routing.items():
        if r == "UNKNOWN":
            cred = _cred_by_id(state, cid) or {}
            await _emit(run_id, "escalation", cred_id=cid, stage="reconcile",
                        reason=cred.get("tls_error") or "coverage could not be determined")
    owned = [cid for cid, r in routing.items() if r in ("OWN_UNMANAGED", "OWN_STALE")]
    assessments: dict[str, Any] = {}
    for cid in owned:
        cred = _cred_by_id(state, cid)
        if not cred:
            continue
        a = assess_credential(cred)
        a["expiry_source"] = cred.get("expiry_source", "simulated")
        if cred.get("not_after"):
            a["not_after"] = cred["not_after"]
        assessments[cid] = {"assessment": a}
        await _emit(
            run_id, "assessment_item",
            cred_id=cid, label=a["label"], kind=a["kind"],
            days_to_expiry=a["days_to_expiry"], not_after=a["not_after"], expired=a["expired"],
            consumers=a["consumers"], consumer_count=a["consumer_count"],
            safe_to_rotate=a["safe_to_rotate"], blocked_reason=a["blocked_reason"],
            expiry_source=a["expiry_source"],
        )
        await asyncio.sleep(0.15)
        if not a["safe_to_rotate"]:
            await _emit(run_id, "escalation", cred_id=cid, stage="assess",
                        reason=a["blocked_reason"])
    return {"assessments": assessments, "status": "assessed"}


async def prioritize(state: SentinelState) -> dict[str, Any]:
    run_id = state["run_id"]
    await _emit(run_id, "node_update", node="prioritize",
                message="Scoring urgency (deterministic)…")
    await asyncio.sleep(0.2)
    assessments = dict(state.get("assessments", {}))
    scored: list[tuple[str, int]] = []
    for cid, entry in assessments.items():
        a = entry["assessment"]
        if not a["safe_to_rotate"]:
            continue  # blocked → escalated, not queued
        u = score_urgency(a)
        entry["urgency"] = u
        assessments[cid] = entry
        scored.append((cid, u["score"]))
        await _emit(run_id, "urgency_item", cred_id=cid, label=a["label"],
                    score=u["score"], band=u["band"], breakdown=u["breakdown"])
        await asyncio.sleep(0.1)
    scored.sort(key=lambda x: x[1], reverse=True)
    queue = [cid for cid, _ in scored]
    await _emit(run_id, "node_update", node="prioritize",
                message=f"{len(queue)} credential(s) prioritized for planning")
    return {"assessments": assessments, "queue": queue, "status": "prioritized"}


async def plan(state: SentinelState) -> dict[str, Any]:
    run_id = state["run_id"]
    source = "Nebius Token Factory" if nebius_configured() else "deterministic fallback"
    await _emit(run_id, "node_update", node="plan", message=f"Drafting rotation plans ({source})…")
    assessments = state.get("assessments", {})
    plans: dict[str, Any] = {}
    for cid in state.get("queue", []):
        a = assessments[cid]["assessment"]
        facts = {
            "cred_id": cid, "kind": a["kind"], "label": a["label"],
            "days_to_expiry": a["days_to_expiry"], "expired": a["expired"],
            "consumers": a["consumers"], "rotation_difficulty": a["rotation_difficulty"],
        }
        p = await draft_plan(facts)
        plans[cid] = p
        await _emit(run_id, "plan_drafted", cred_id=cid, label=a["label"],
                    source=p["source"], impact_summary=p["impact_summary"], steps=p["steps"])
    await _emit(run_id, "node_update", node="plan", message=f"{len(plans)} plan(s) drafted")
    return {"plans": plans, "status": "awaiting_staging_approval"}


async def gate_staging(state: SentinelState) -> dict[str, Any]:
    """Gate 1 — approve which credentials may be staged. Pure interrupt (re-runs
    from the top on resume), so it only assembles the payload."""
    assessments = state.get("assessments", {})
    plans = state.get("plans", {})
    items = []
    for cid in state.get("queue", []):
        a = assessments[cid]["assessment"]
        u = assessments[cid].get("urgency", {})
        items.append({
            "cred_id": cid, "label": a["label"], "kind": a["kind"],
            "proposed_action": "stage_credential",
            "days_to_expiry": a["days_to_expiry"], "not_after": a["not_after"],
            "expired": a["expired"], "expiry_source": a.get("expiry_source", "simulated"),
            "consumers": a["consumers"], "consumer_count": a["consumer_count"],
            "urgency": u, "plan": plans.get(cid),
        })
    decision = interrupt({"gate": "staging", "items": items})
    return {"staging_decisions": decision, "status": "staging"}


async def stage(state: SentinelState) -> dict[str, Any]:
    run_id = state["run_id"]
    max_attempts = int(load_policy()["retries"]["staging_max_attempts"])
    decision = state.get("staging_decisions") or {}
    approved = [d["cred_id"] for d in decision.get("decisions", []) if d.get("action") == "approve"]
    await _emit(run_id, "node_update", node="stage",
                message=f"Staging {len(approved)} approved credential(s) (max {max_attempts} attempts)…")
    results: dict[str, Any] = {}
    for cid in approved:
        cred = _cred_by_id(state, cid)
        outcome = (cred or {}).get("sim_stage_outcome", "healthy")
        attempts, healthy = 0, False
        while attempts < max_attempts:
            attempts += 1
            await _emit(run_id, "staging_attempt", cred_id=cid, attempt=attempts, status="validating")
            await asyncio.sleep(0.4)
            if outcome == "healthy" or (outcome == "flaky" and attempts >= 2):
                healthy = True
                break
            await _emit(run_id, "staging_attempt", cred_id=cid, attempt=attempts, status="failed")
        if healthy:
            results[cid] = {"status": "staged_healthy", "attempts": attempts}
            await _emit(run_id, "staging_result", cred_id=cid, status="staged_healthy", attempts=attempts)
        else:
            results[cid] = {"status": "staged_unhealthy", "attempts": attempts, "escalated": True}
            await _emit(run_id, "staging_result", cred_id=cid, status="staged_unhealthy", attempts=attempts)
            await _emit(run_id, "escalation", cred_id=cid, stage="staging",
                        reason="replacement unhealthy after retries; live credential left untouched")
    return {"staging_results": results, "status": "awaiting_cutover_approval"}


# --------------------------------------------------------------------------- #
# Phase 0/3 (still simulated)
# --------------------------------------------------------------------------- #
async def gate_cutover(state: SentinelState) -> dict[str, Any]:
    """Gate 2 — approve each cutover. Only staged-healthy credentials qualify."""
    labels = _labels(state)
    healthy = [
        cid for cid, r in state.get("staging_results", {}).items()
        if r.get("status") == "staged_healthy"
    ]
    items = [
        {"cred_id": cid, "label": labels.get(cid, cid), "proposed_action": "cutover_and_revoke"}
        for cid in healthy
    ]
    decision = interrupt({"gate": "cutover", "items": items})
    return {"cutover_decisions": decision, "status": "cutover"}


async def cutover(state: SentinelState) -> dict[str, Any]:
    """Cut over with **delayed revocation** (ADR-6): the old credential is revoked
    only after the new one is promoted, consumers repointed, and health verified.
    If verification fails, repoint back to the still-valid old credential and
    escalate — nothing is lost (Feature A: auto-rollback)."""
    run_id = state["run_id"]
    decision = state.get("cutover_decisions") or {}
    approved = [d["cred_id"] for d in decision.get("decisions", []) if d.get("action") == "approve"]
    results: dict[str, Any] = {}
    for cid in approved:
        cred = _cred_by_id(state, cid)
        outcome = (cred or {}).get("sim_cutover_outcome", "healthy")

        await asyncio.sleep(0.35)
        await _emit(run_id, "cutover_step", cred_id=cid, step="promote", status="ok")
        await asyncio.sleep(0.35)
        await _emit(run_id, "cutover_step", cred_id=cid, step="repoint", status="ok")
        await asyncio.sleep(0.4)

        if outcome == "healthy":
            await _emit(run_id, "cutover_step", cred_id=cid, step="verify", status="ok")
            await asyncio.sleep(0.35)
            # Old credential still valid up to here; revoke only now (delayed).
            await _emit(run_id, "cutover_step", cred_id=cid, step="revoke_old", status="ok")
            results[cid] = {"status": "cutover_complete"}
            await _emit(run_id, "cutover_result", cred_id=cid, status="cutover_complete")
        else:
            await _emit(run_id, "cutover_step", cred_id=cid, step="verify", status="failed")
            await asyncio.sleep(0.35)
            # Old credential was never revoked → roll consumers back to it.
            await _emit(run_id, "cutover_step", cred_id=cid, step="rollback", status="ok")
            results[cid] = {"status": "rolled_back", "escalated": True}
            await _emit(run_id, "cutover_result", cred_id=cid, status="rolled_back")
            await _emit(
                run_id, "escalation", cred_id=cid, stage="cutover",
                reason="post-cutover verification failed; rolled back to old credential (still valid) — nothing lost",
            )
    return {"cutover_results": results, "status": "reporting"}


async def report(state: SentinelState) -> dict[str, Any]:
    run_id = state["run_id"]

    # 1) Disposition + summary for this run, then diff against the prior sweep.
    await _emit(run_id, "node_update", node="report", message="Diffing coverage against the prior sweep…")
    summary = build_summary(dict(state))
    prior = await memory.latest_prior_summary(run_id)
    drift = compute_drift(prior, summary)
    await _emit(run_id, "drift_summary", **drift)
    await memory.save_summary(run_id, summary)

    # 2) Counts for the report.
    counts: dict[str, int] = {"discovered": len(state.get("live_inventory", []))}
    for c in summary["creds"].values():
        counts[c["disposition"]] = counts.get(c["disposition"], 0) + 1
    counts.setdefault("deferred", 0)
    counts.setdefault("cut_over", 0)
    counts.setdefault("rolled_back", 0)
    counts.setdefault("escalated", 0)

    # 3) Narrative via Nebius (fallback if unconfigured).
    src = "Nebius Token Factory" if nebius_configured() else "deterministic fallback"
    await _emit(run_id, "node_update", node="report", message=f"Writing run report ({src})…")
    report_doc = await draft_report({"counts": counts, "drift": drift})
    await _emit(
        run_id, "report_ready",
        headline=report_doc["headline"], narrative=report_doc["narrative"],
        source=report_doc["source"], counts=counts,
    )
    return {"status": "completed", "drift": drift, "run_report": {**report_doc, "counts": counts}}
