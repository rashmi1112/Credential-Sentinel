"""Cross-run memory: a compact summary of each run, so the next run can diff
against it for coverage drift (Feature B). Its own SQLite file, single writer."""
from __future__ import annotations

import json
import time
from typing import Any, Optional

import aiosqlite

_db_path: Optional[str] = None


def configure(path: str) -> None:
    global _db_path
    _db_path = path


async def _connect() -> aiosqlite.Connection:
    assert _db_path
    db = await aiosqlite.connect(_db_path)
    await db.execute("PRAGMA busy_timeout=5000")
    return db


async def init_db() -> None:
    db = await _connect()
    try:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(
            "CREATE TABLE IF NOT EXISTS run_summaries "
            "(run_id TEXT PRIMARY KEY, ts REAL NOT NULL, summary TEXT NOT NULL)"
        )
        await db.commit()
    finally:
        await db.close()


async def save_summary(run_id: str, summary: dict[str, Any]) -> None:
    db = await _connect()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO run_summaries (run_id, ts, summary) VALUES (?, ?, ?)",
            (run_id, time.time(), json.dumps(summary)),
        )
        await db.commit()
    finally:
        await db.close()


async def latest_prior_summary(run_id: str) -> Optional[dict[str, Any]]:
    """The most recent summary from a *different* run (the prior sweep)."""
    db = await _connect()
    try:
        cur = await db.execute(
            "SELECT run_id, summary FROM run_summaries WHERE run_id != ? ORDER BY ts DESC LIMIT 1",
            (run_id,),
        )
        row = await cur.fetchone()
    finally:
        await db.close()
    if not row:
        return None
    return {"run_id": row[0], **json.loads(row[1])}
