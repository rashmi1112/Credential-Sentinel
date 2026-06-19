# Unmanaged Credential Sentinel

> An agentic system that finds the credentials no rotation service is tracking, and drives them to a safe, human-approved rotation.

The rotation *mechanism* is a commodity (AWS Secrets Manager, Vault, cert-manager). This agent is the **discovery and decisioning layer** around it: it reconciles live production credentials against what the rotation services actually manage, then safely handles the unmanaged tail that falls through the cracks, with a human gate before any staged credential is created and before every cutover.

The sections below summarize the design, architecture, and run instructions.

---

## Status: Phases 0–4 done (code complete)

**Phase 0 (walking skeleton)** — proven plumbing:
- ✅ LangGraph graph with a SQLite checkpointer and **two interrupt gates**
- ✅ Stateless FastAPI over a stateful graph — `run_id == thread_id`, every call resumes from the checkpoint
- ✅ **SSE** live progress backed by a persisted event log (replays on reconnect)
- ✅ Next.js + shadcn/ui frontend: dashboard, activity feed, reconciliation table, approval gates
- ✅ Real-browser Playwright e2e through both gates

**Phase 1 (discovery + reconciliation)** — partly real:
- ✅ **Real TLS adapter** — a genuine TLS handshake reads `notAfter` from the live cert (`ssl` + `cryptography`), with bounded retry/backoff. `expired.badssl.com` is detected as really expired; this real expiry feeds the urgency score.
- ✅ `reconcile_coverage` follows the 5.4 decision tree: in a managed store & rotating → DEFER; in a store but not rotating → OWN_STALE; absent → OWN_UNMANAGED; unreachable/unclassifiable → **UNKNOWN** (escalated, never assumed safe — ADR-4)
- 🟡 Token/config-scan discovery sources stay simulated (ADR-3); only TLS is live. Pluggable adapter interfaces + a dedicated partial-view report are still to come.

**Phase 2 (assess / prioritize / plan / stage)** — real logic:
- ✅ `assess` — days-to-expiry, consumer enumeration, rotation safety (blocks if consumers can't be fully enumerated)
- ✅ `prioritize` — transparent urgency score = f(expiry, blast radius, difficulty), ranked queue (ADR-7)
- ✅ `plan` — **Nebius Token Factory** call drafting the rotation plan, with a deterministic fallback when no key is set
- ✅ `stage_and_validate` — bounded retry (policy.yaml) + **staged-but-unhealthy escalation** (live credential left untouched)
- ✅ Gate 1 shows urgency + expiry + blast radius + the drafted plan (with a **live TLS** marker); a staging panel shows outcomes

**Phase 3 (cutover / verify / rollback)** — the irreversible write path, gated and recoverable:
- ✅ `cutover` with **delayed-revoke ordering** (ADR-6): promote → repoint → verify, and the old credential is revoked *only after* verification passes
- ✅ **Auto-rollback (Feature A)** — if post-cutover verification fails, consumers repoint back to the still-valid old credential and the run escalates; nothing is lost
- ✅ `CutoverPanel` shows the live sequence and per-credential outcome (cut over vs rolled back)
- ✅ e2e exercises both: one credential cuts over (old revoked), one rolls back on a failed verify

**Phase 4 (memory + report)** — the elevating features:
- ✅ **Coverage drift memory (Feature B)** — each run persists a compact summary; the next run diffs against it to surface newly discovered unmanaged credentials, changed coverage, and items **stuck across cycles**. Rendered in the `DriftPanel`.
- ✅ `report` node — a **Nebius**-written end-of-run narrative + counts (fallback when no key), shown in the `ReportPanel`
- ✅ Cross-run memory lives in its own SQLite file (`sentinel_memory.db`); the run event log doubles as the audit trail

All five build phases are code-complete. Remaining work is the **deliverables**: record the demo video, write the project Google Doc, and push to GitHub.

### TLS mode
`discover` does a real TLS handshake by default. Set `SENTINEL_TLS_MODE=sim` to skip it (offline/deterministic — used by the tests).

---

## Architecture

```
Next.js (shadcn/ui)  --REST + SSE-->  FastAPI  <-->  LangGraph (2 interrupt gates)  <-->  Nebius (plan)
                                         |                  |
                                         +----- SQLite -----+   (checkpointer + event log, separate files)
```

The graph:
`discover → list_managed → reconcile → assess → prioritize → plan → [Gate 1: staging] → stage → [Gate 2: cutover] → cutover → report`

### Nebius Token Factory (the model call)

The `plan` node calls Nebius (OpenAI-compatible). Add your key to `backend/.env`:

```
NEBIUS_API_KEY=sk-...           # leave blank to use the deterministic fallback
NEBIUS_MODEL=meta-llama/Llama-3.3-70B-Instruct
```

Without a key it falls back to a deterministic plan, so the app always runs. The prompt passes credential metadata as untrusted **data** (injection guard) and never handles secret values.

---

## Running it

### Backend (FastAPI + LangGraph) — `:8000`

```bash
cd backend
python3.11 -m venv .venv          # needs Python 3.10+
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Headless end-to-end check (no browser, no server):

```bash
cd backend && .venv/bin/python smoke_test.py
```

### Frontend (Next.js) — `:3000`

```bash
cd frontend
npm install
npm run dev
```

`frontend/.env.local` points the UI at the backend (`NEXT_PUBLIC_API=http://localhost:8000`).

Then open <http://localhost:3000>, click **Start a new sweep**, watch the fake events stream, approve/reject at Gate 1, watch it stage, approve/reject at Gate 2, and watch it cut over and complete.

### Browser end-to-end test (Playwright)

A real-browser test boots both servers, starts a sweep, clears both gates, and asserts the run completes:

```bash
cd frontend
npm run e2e        # playwright test (starts backend + frontend automatically)
```

> Note on storage: the LangGraph checkpointer and the SSE event log live in **two
> separate SQLite files** (`sentinel.db` and `sentinel_events.db`). The
> checkpointer holds a long-lived connection and a write lock across interrupt
> pauses; keeping the event log in its own file means each file has a single
> writer and the two never deadlock.

---

## API surface

| Method + path | Purpose |
|---|---|
| `POST /api/runs` | Create a run (`run_id = thread_id`); streams the graph to the next interrupt. Returns `{ run_id }`. |
| `GET /api/runs/{id}/events` | SSE stream; replays the persisted log on reconnect. |
| `POST /api/runs/{id}/decisions` | `{ gate, decisions: [{ cred_id, action }] }` → resumes via `Command(resume=...)`. Returns `202`. |
| `GET /api/runs/{id}` | Snapshot: reconciliation, queue, staging results, pending gate. |
| `GET /api/runs` | List runs. |
| `GET /api/runs/{id}/audit` | Audit / event log for the run. |

---

## Layout

```
backend/
  app/
    main.py              # FastAPI app, CORS, lifespan-managed graph + checkpointer
    api/runs.py          # the run endpoints + SSE
    graph/
      state.py           # SentinelState
      build.py           # build_graph() -> compiled graph with 2 interrupts
      nodes.py           # Phase 0 stubbed nodes
    services/
      events.py          # per-run pub/sub + SQLite persistence for SSE replay
      runner.py          # run_segment(): drives the graph to the next gate / completion
    core/config.py       # env + paths (Nebius wired but unused in Phase 0)
  smoke_test.py          # headless end-to-end graph test
frontend/
  app/page.tsx                 # dashboard
  app/runs/[runId]/page.tsx    # run detail
  components/                  # ActivityFeed, ReconciliationTable, ApprovalGate, ui/ (shadcn)
  lib/                         # api.ts, useRunStream.ts (SSE hook), types.ts
  e2e/walking-skeleton.spec.ts # Playwright: clicks through both gates to completion
  playwright.config.ts         # boots backend + frontend for the test
```
