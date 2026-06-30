"""FastAPI app: CORS, lifespan-managed graph + checkpointer, run router."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

from .api.runs import router as runs_router
from .core.config import ALLOWED_ORIGINS, DB_PATH, EVENTS_DB_PATH, MEMORY_DB_PATH
from .graph.build import build_graph
from .services import memory
from .services.events import broker

_REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
_REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)


class _PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        _REQUEST_LATENCY.labels(method=request.method, path=request.url.path).observe(
            time.perf_counter() - t0
        )
        _REQUEST_COUNT.labels(
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        ).inc()
        return response


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

app.add_middleware(_PrometheusMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs_router)


@app.get("/metrics", include_in_schema=False)
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
