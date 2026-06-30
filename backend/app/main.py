"""FastAPI app: CORS, lifespan-managed graph + checkpointer, run router."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from prometheus_fastapi_instrumentator import Instrumentator

from .api.runs import router as runs_router
from .core.config import ALLOWED_ORIGINS, DB_PATH, EVENTS_DB_PATH, MEMORY_DB_PATH
from .graph.build import build_graph
from .services import memory
from .services.events import broker


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Event log + cross-run memory each get their own file; the checkpointer owns
    # DB_PATH exclusively (separate files → no write contention).
    broker.configure(EVENTS_DB_PATH)
    await broker.init_db()
    memory.configure(MEMORY_DB_PATH)
    await memory.init_db()
    # One AsyncSqliteSaver open for the app's lifetime; every request resumes
    # from it by thread_id. It is the only writer of DB_PATH.
    async with AsyncSqliteSaver.from_conn_string(DB_PATH) as saver:
        app.state.graph = build_graph(saver)
        yield


app = FastAPI(title="Unmanaged Credential Sentinel", version="0.0-skeleton", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs_router)

# Expose /metrics in Prometheus format — HTTP request counts, latency histograms,
# and in-flight request gauges for every endpoint, automatically.
Instrumentator().instrument(app).expose(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
