"""Simulated discovery + managed-inventory data (ADR-3: honest simulation boundary).

Phase 1 will replace this with real adapters (incl. a real TLS handshake against
``endpoint``). For now the fields are realistic enough that the Phase 2 assess /
prioritize / plan / stage logic operates on genuine structure — only the *source*
of these credentials is simulated.

``not_after_days`` is relative to "now" so days-to-expiry is stable per run.
``sim_stage_outcome`` drives the staging simulation:
  - "healthy"   → stages and validates first try
  - "flaky"     → first validation attempt fails, heals on retry (exercises retry)
  - "unhealthy" → validation never passes → escalate, live credential untouched

``sim_cutover_outcome`` drives the cutover simulation (Phase 3):
  - "healthy"   → consumers verify healthy on the new credential → revoke old (delayed)
  - "unhealthy" → post-cutover verification fails → roll back to old (still valid), escalate
"""
from __future__ import annotations

from typing import Any

SIM_LIVE: list[dict[str, Any]] = [
    {
        "id": "tls-lb-01",
        "kind": "tls_cert",
        "label": "prod-lb TLS cert",
        "endpoint": "expired.badssl.com:443",
        "not_after_days": -3,  # already expired
        "consumers": ["prod-lb", "api-gateway", "checkout-svc"],
        "consumers_complete": True,
        "rotation_difficulty": "medium",
        "sim_stage_outcome": "flaky",
        "sim_cutover_outcome": "healthy",  # verifies healthy → old revoked (delayed)
    },
    {
        "id": "sa-key-vm3",
        "kind": "sa_key",
        "label": "service-account key on vm3",
        "endpoint": None,
        "not_after_days": 11,
        "consumers": ["batch-runner-vm3"],
        "consumers_complete": True,
        "rotation_difficulty": "easy",
        "sim_stage_outcome": "healthy",
        "sim_cutover_outcome": "unhealthy",  # verify fails after cutover → auto-rollback
    },
    {
        "id": "api-key-legacy",
        "kind": "saas_token",
        "label": "legacy payments API key",
        "endpoint": None,
        "not_after_days": 21,
        "consumers": ["billing-svc", "reconciliation-job"],
        "consumers_complete": True,
        "rotation_difficulty": "medium",
        "sim_stage_outcome": "unhealthy",  # demonstrates staged-but-unhealthy escalation
    },
    {
        "id": "tok-ci-7",
        "kind": "saas_token",
        "label": "CI Slack token",
        "endpoint": None,
        "not_after_days": 40,
        "consumers": ["ci-pipeline"],
        "consumers_complete": True,
        "rotation_difficulty": "easy",
        "sim_stage_outcome": "healthy",
    },
]

# What the rotation services claim to manage. tok-ci-7 is owned by Vault and
# actively rotating → defer. sa-key-vm3 is in AWS SM but its rotation is disabled
# (managed-but-unrotating) → the agent owns it as OWN_STALE.
SIM_MANAGED: list[dict[str, Any]] = [
    {"id": "tok-ci-7", "store": "vault", "rotating": True},
    {"id": "sa-key-vm3", "store": "aws_sm", "rotating": False},
]


def by_id(cred_id: str) -> dict[str, Any] | None:
    for c in SIM_LIVE:
        if c["id"] == cred_id:
            return c
    return None
