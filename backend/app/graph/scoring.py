"""Deterministic, explainable assessment + urgency (ADR-7).

Pure functions — no I/O, no LLM — so they're trivially testable and the urgency
score is a transparent function of days-to-expiry, blast radius, and rotation
difficulty, never a model judgment.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

_DIFFICULTY_WEIGHT = {"easy": 0, "medium": 6, "hard": 12}


def assess_credential(cred: dict[str, Any]) -> dict[str, Any]:
    """Turn a discovered credential into an assessment. Safety rule: never rotate
    a credential whose consumers cannot be fully enumerated."""
    dte = int(cred.get("not_after_days", 0))
    consumers = list(cred.get("consumers", []))
    complete = bool(cred.get("consumers_complete", True))
    not_after = (date.today() + timedelta(days=dte)).isoformat()
    return {
        "cred_id": cred["id"],
        "kind": cred["kind"],
        "label": cred.get("label", cred["id"]),
        "days_to_expiry": dte,
        "not_after": not_after,
        "expired": dte < 0,
        "consumers": consumers,
        "consumer_count": len(consumers),
        "consumers_complete": complete,
        "rotation_difficulty": cred.get("rotation_difficulty", "medium"),
        "safe_to_rotate": complete,
        "blocked_reason": None if complete else "consumers cannot be fully enumerated",
    }


def _expiry_component(assessment: dict[str, Any]) -> int:
    if assessment["expired"]:
        return 100
    dte = assessment["days_to_expiry"]
    if dte <= 7:
        return 90
    if dte <= 14:
        return 72
    if dte <= 30:
        return 50
    if dte <= 60:
        return 30
    return 12


def score_urgency(assessment: dict[str, Any]) -> dict[str, Any]:
    """Transparent 0–100 urgency = weighted expiry + blast radius + difficulty."""
    expiry = _expiry_component(assessment)
    blast = min(assessment["consumer_count"], 6) * 4  # 0..24
    difficulty = _DIFFICULTY_WEIGHT.get(assessment["rotation_difficulty"], 6)
    score = min(100, round(0.7 * expiry + blast + difficulty))
    band = (
        "critical" if score >= 85
        else "high" if score >= 60
        else "medium" if score >= 35
        else "low"
    )
    return {
        "score": score,
        "band": band,
        "breakdown": {"expiry": expiry, "blast_radius": blast, "difficulty": difficulty},
    }
