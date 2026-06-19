"""Load policy.yaml (ADR-9: policy as config). Falls back to sane defaults."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from .config import BASE_DIR

_POLICY_PATH = BASE_DIR.parent / "policy.yaml"

_DEFAULTS: dict[str, Any] = {
    "expiry_windows": {"tls_cert_days": 30, "saas_token_days": 14, "sa_key_days": 90},
    "retries": {"discovery_max_attempts": 3, "staging_max_attempts": 3, "backoff_seconds": 2},
}


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    try:
        with open(_POLICY_PATH) as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        return dict(_DEFAULTS)
    # shallow-merge over defaults so missing keys still resolve
    merged = {**_DEFAULTS, **data}
    for k, v in _DEFAULTS.items():
        if isinstance(v, dict):
            merged[k] = {**v, **(data.get(k) or {})}
    return merged
