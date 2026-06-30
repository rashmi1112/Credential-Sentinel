"""Environment + path configuration for the Sentinel backend."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Repo-relative data dir so the SQLite file survives reloads.
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# SENTINEL_DB (relative to backend/ or absolute) overrides the default DB file;
# the e2e suite points this at a throwaway DB.
_db_override = os.getenv("SENTINEL_DB")
if _db_override:
    _p = Path(_db_override)
    DB_PATH = str(_p if _p.is_absolute() else BASE_DIR / _p)
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
else:
    DB_PATH = str(DATA_DIR / "sentinel.db")

# The event log lives in its OWN SQLite file. The LangGraph checkpointer holds a
# long-lived connection (and a write lock across interrupts) on DB_PATH; keeping
# the event log separate means each file has a single writer and the two never
# contend. (ADR-8 envisions one file; this is the honest Phase 0 split.)
EVENTS_DB_PATH = str(Path(DB_PATH).with_name(Path(DB_PATH).stem + "_events.db"))

# Cross-run memory (coverage-drift detection). Its own file → single writer, no
# contention with the checkpointer or the event log.
MEMORY_DB_PATH = str(Path(DB_PATH).with_name(Path(DB_PATH).stem + "_memory.db"))

# Frontend origin allowed through CORS (Next.js dev server).
ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]

# Discovery: "real" does a live TLS handshake for tls_cert credentials; "sim"
# uses the simulated not_after_days (offline/deterministic, for tests).
TLS_MODE = os.getenv("SENTINEL_TLS_MODE", "real").lower()

# Eval mode (Week 4): skip the cosmetic SSE-pacing sleeps so latency/cost metrics
# reflect real node compute + LLM time, not demo pacing. Off by default.
EVAL_MODE = os.getenv("SENTINEL_EVAL_MODE", "").lower() in ("1", "true", "yes")

# Nebius Token Factory (unused in Phase 0; wired so later phases just work).
NEBIUS_API_KEY = os.getenv("NEBIUS_API_KEY", "")
NEBIUS_BASE_URL = os.getenv("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1/")
NEBIUS_MODEL = os.getenv("NEBIUS_MODEL", "meta-llama/Llama-3.3-70B-Instruct")
