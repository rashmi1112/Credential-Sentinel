"""Per-run event broker: in-memory pub/sub plus SQLite persistence.

Every event is persisted with a monotonic per-run ``seq`` so a reconnecting SSE
client can replay from the log and then pick up live events without gaps or
duplicates (ADR-13). Nodes publish granular events directly; the runner
publishes the gate and completion events.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import aiosqlite


class EventBroker:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue]] = {}
        self._db_path: str | None = None
        self._write_lock = asyncio.Lock()

    def configure(self, db_path: str) -> None:
        self._db_path = db_path

    async def _connect(self) -> aiosqlite.Connection:
        db = await aiosqlite.connect(self._db_path)
        # Wait instead of erroring when the checkpointer holds the write lock.
        await db.execute("PRAGMA busy_timeout=5000")
        return db

    async def init_db(self) -> None:
        assert self._db_path
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS run_events (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id  TEXT    NOT NULL,
                    seq     INTEGER NOT NULL,
                    ts      REAL    NOT NULL,
                    event   TEXT    NOT NULL
                )
                """
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_run_events_run ON run_events(run_id, seq)"
            )
            await db.commit()

    async def publish(self, run_id: str, event: dict[str, Any]) -> dict[str, Any]:
        assert self._db_path
        enriched = {**event, "ts": event.get("ts", time.time())}
        # Serialize writes so per-run seq numbers stay monotonic.
        async with self._write_lock:
            db = await self._connect()
            try:
                cur = await db.execute(
                    "SELECT COALESCE(MAX(seq), 0) + 1 FROM run_events WHERE run_id = ?",
                    (run_id,),
                )
                row = await cur.fetchone()
                enriched["seq"] = int(row[0]) if row else 1
                await db.execute(
                    "INSERT INTO run_events (run_id, seq, ts, event) VALUES (?, ?, ?, ?)",
                    (run_id, enriched["seq"], enriched["ts"], json.dumps(enriched)),
                )
                await db.commit()
            finally:
                await db.close()
        for q in list(self._subs.get(run_id, ())):
            await q.put(enriched)
        return enriched

    async def replay(self, run_id: str) -> list[dict[str, Any]]:
        assert self._db_path
        db = await self._connect()
        try:
            cur = await db.execute(
                "SELECT event FROM run_events WHERE run_id = ? ORDER BY seq",
                (run_id,),
            )
            rows = await cur.fetchall()
        finally:
            await db.close()
        return [json.loads(r[0]) for r in rows]

    async def list_runs(self) -> list[dict[str, Any]]:
        """Distinct runs with a coarse status, for the dashboard / drift view."""
        assert self._db_path
        db = await self._connect()
        try:
            cur = await db.execute(
                """
                SELECT run_id, MIN(ts) AS started, MAX(ts) AS updated, COUNT(*) AS n
                FROM run_events GROUP BY run_id ORDER BY started DESC
                """
            )
            rows = await cur.fetchall()
            out = []
            for run_id, started, updated, n in rows:
                cur2 = await db.execute(
                    "SELECT event FROM run_events WHERE run_id = ? ORDER BY seq DESC LIMIT 1",
                    (run_id,),
                )
                last = await cur2.fetchone()
                last_ev = json.loads(last[0]) if last else {}
                out.append(
                    {
                        "run_id": run_id,
                        "started_at": started,
                        "updated_at": updated,
                        "event_count": n,
                        "last_event_type": last_ev.get("type"),
                    }
                )
            return out
        finally:
            await db.close()

    def subscribe(self, run_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(run_id, set()).add(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(run_id)
        if subs:
            subs.discard(q)
            if not subs:
                self._subs.pop(run_id, None)


broker = EventBroker()
