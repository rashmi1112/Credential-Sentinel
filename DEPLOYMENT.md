# Deployment Guide: Credential Sentinel

This document explains every deployment tool and platform used in this project —
what it is, why we chose it, how it fits together, and what we would have done
differently if our constraints were different.

---

## Table of Contents

1. [The Problem: Why "deploy it" matters at all](#1-the-problem)
2. [Docker — packaging the app](#2-docker--packaging-the-app)
3. [Multi-stage builds — keeping images small](#3-multi-stage-builds--keeping-images-small)
4. [Docker Compose — running multiple services together](#4-docker-compose--running-multiple-services-together)
5. [vLLM — self-hosted LLM inference](#5-vllm--self-hosted-llm-inference)
6. [Kubernetes — production orchestration](#6-kubernetes--production-orchestration)
7. [Fly.io — the fastest path to a real public URL](#7-flyio--the-fastest-path-to-a-real-public-url)
8. [Prometheus — observability](#8-prometheus--observability)
9. [The latency benchmark](#9-the-latency-benchmark)
10. [Key architectural decisions and tradeoffs](#10-key-architectural-decisions-and-tradeoffs)
11. [What's next: Terraform and Triton](#11-whats-next-terraform-and-triton)
12. [How all the pieces connect](#12-how-all-the-pieces-connect)

---

## 1. The Problem

When you build an AI agent locally, it runs fine on your laptop. But a recruiter or
a production team doesn't care about your laptop. They care about:

- **Can it run anywhere?** — not just on your machine with your exact Python version
- **Can it handle traffic?** — multiple people using it at the same time
- **Can you see what it's doing in production?** — logs, metrics, alerts
- **Can you update it without downtime?** — rolling deployments
- **Can it use a real model server?** — not just the cheapest hosted API

This document explains how we answered each of those questions for the
Credential Sentinel agent.

---

## 2. Docker — packaging the app

### What it is

Docker packages your application and all its dependencies (Python version, pip
packages, system libraries, config files) into a single artifact called an
**image**. When someone runs that image, they get a **container** — an isolated
process that behaves identically regardless of what machine it's on.

Think of it like a shipping container. Before shipping containers, every port
had to figure out how to load each cargo shipment differently. Shipping
containers standardized the interface so any ship, any crane, any truck could
handle any container. Docker does the same for software.

### What we built

Two Dockerfiles:

**`backend/Dockerfile`** (build from the repo root):
```
docker build -f backend/Dockerfile -t sentinel-backend .
docker run -p 8000:8000 -v sentinel_data:/app/data sentinel-backend
```

**`frontend/Dockerfile`** (build from the `frontend/` directory):
```
docker build -f frontend/Dockerfile -t sentinel-frontend \
  --build-arg NEXT_PUBLIC_API=http://localhost:8000 frontend/
docker run -p 3000:3000 sentinel-frontend
```

### One non-obvious detail: `policy.yaml`

The backend reads `policy.yaml` from the repository root (one level above the
`backend/` folder). Inside the container, the app lives at `/app/`, so the
policy file needs to be at `/policy.yaml`. The Dockerfile handles this:

```dockerfile
COPY policy.yaml /policy.yaml
```

We use the repo root as the Docker **build context** for the backend so both
`backend/` and `policy.yaml` are accessible to the Dockerfile. This is why the
build command is `docker build -f backend/Dockerfile .` from the repo root
(the `.` means "use the current directory as context").

### Why Docker instead of just `pip install`?

| Approach | Problem |
|---|---|
| `pip install` on a server | "It works on my machine" — Python versions, OS libs, and transitive deps differ |
| Virtual environments | Still tied to the OS Python, and you have to set them up on every server |
| Docker image | One artifact, runs identically everywhere |

The alternative would be a VM image (like an AWS AMI or a GCP machine image).
Docker images are smaller, faster to build, faster to start, and are the
standard for cloud-native workloads today.

---

## 3. Multi-stage builds — keeping images small

### What it is

A naive Dockerfile copies all your source code and build tools into one image.
The problem: build tools (the Node.js compiler, npm, dev dependencies) are
large and are not needed at runtime. A multi-stage build uses a series of
`FROM` statements, where each stage can copy artifacts from earlier stages and
discard everything else.

### What we built

The frontend Dockerfile has three stages:

```
Stage 1 (deps):    Install npm dependencies
Stage 2 (builder): Run `npm run build` to compile the Next.js app
Stage 3 (runtime): Copy only the compiled output — no node_modules, no source code
```

The runtime image is roughly **10× smaller** than a naive single-stage build
because it contains only what's needed to run the app, not to build it.

We also enabled **Next.js standalone mode** by adding `output: "standalone"` to
`next.config.ts`. In standalone mode, Next.js bundles only the node_modules
actually used at runtime into a single `server.js` file. Without this, you'd
have to copy the entire `node_modules/` directory (hundreds of megabytes) into
the image. With it, the runtime image is a few dozen megabytes.

### Why this matters

Smaller images mean:
- Faster to push and pull from a container registry (lower latency when deploying)
- Less attack surface (fewer packages = fewer potential vulnerabilities)
- Cheaper storage in registries like Docker Hub or GitHub Container Registry

---

## 4. Docker Compose — running multiple services together

### What it is

The Credential Sentinel application has three services: the backend (FastAPI),
the frontend (Next.js), and optionally a local LLM inference server (vLLM).
Running `docker run` for each one separately is tedious and error-prone.
**Docker Compose** lets you define all services in one `docker-compose.yml` file
and start them all with `docker compose up`.

### What we built

`docker-compose.yml` defines:

- `backend` — FastAPI on port 8000, with a named volume for SQLite data
- `frontend` — Next.js on port 3000, waits for backend to be healthy before starting
- `vllm` — only starts when you explicitly ask for it (explained in the next section)

```bash
# Standard local dev (uses Nebius for LLM calls):
docker compose up

# With self-hosted LLM inference (requires NVIDIA GPU):
docker compose --profile vllm up
```

### The `vllm` profile

The vLLM service is tagged with `profiles: [vllm]` in the compose file. This
means it doesn't start by default — you have to opt in with `--profile vllm`.
We did this because vLLM requires a GPU, which most development machines don't
have. The base `docker compose up` still works fully using Nebius as the LLM
backend.

### Why Docker Compose instead of separate shell scripts?

Shell scripts for starting multiple services break when services have ordering
dependencies (the frontend should not start until the backend is ready).
Docker Compose handles this with `depends_on` + `condition: service_healthy`,
which means the frontend only starts after the backend passes its health check.

---

## 5. vLLM — self-hosted LLM inference

### What it is

Right now, when the Credential Sentinel agent generates a rotation plan, it
calls the **Nebius API** — a hosted service running a Llama 3.3 70B model in
the cloud. You send it text, it sends back a response, and you pay per token.

**vLLM** is an open-source server that runs the same model yourself, on your
own GPU. It exposes the **exact same API as OpenAI** — same HTTP endpoints,
same JSON format, same Python client. The only difference is the URL you point
the client at.

### The key insight: zero code changes needed

Look at how the backend calls the LLM (`backend/app/core/nebius.py`):

```python
client = AsyncOpenAI(api_key=NEBIUS_API_KEY, base_url=NEBIUS_BASE_URL)
```

`NEBIUS_BASE_URL` is an environment variable. To switch from Nebius to vLLM:

```bash
# Nebius (current default):
NEBIUS_BASE_URL=https://api.studio.nebius.com/v1/

# Self-hosted vLLM:
NEBIUS_BASE_URL=http://localhost:8001/v1/
```

That's it. One environment variable. No code changes. This is the value of
using an **OpenAI-compatible interface** — it's a standard that many inference
servers implement, making them interchangeable.

### Why vLLM specifically?

vLLM was created at UC Berkeley and introduced two major innovations:

1. **PagedAttention** — manages GPU memory the way an operating system manages
   RAM with virtual memory. This lets vLLM serve many more requests concurrently
   on the same GPU compared to naive inference.

2. **Continuous batching** — instead of waiting for a "full batch" of requests
   to arrive before starting inference (static batching), vLLM adds new requests
   to the batch mid-generation. Under concurrent load, this gives much higher
   throughput without significantly increasing latency for individual requests.

### What the benchmark shows

`scripts/latency_bench.py` sends N simultaneous requests and measures P50/P95/P99
latency at each concurrency level. The pattern you typically see:

- **Concurrency = 1**: vLLM and a naive server have similar latency (no batching benefit)
- **Concurrency = 4, 8, 16**: vLLM's P95 stays relatively flat; naive static batching
  makes requests wait in a queue, blowing up P95

This is what interviewers mean when they ask "tell me about your experience with
inference serving and batching/latency tradeoffs."

### Why vLLM instead of Triton Inference Server?

**Triton** (from NVIDIA) is a general-purpose model serving framework. It can
serve any model in any format (PyTorch, TensorFlow, ONNX, TensorRT). Triton is
the right choice when you need:
- Maximum throughput optimization at the hardware level
- Custom preprocessing/postprocessing pipelines
- Ensemble models (multiple models chained together)
- Non-LLM models (image classifiers, embedding models)

**vLLM** is LLM-specific and makes LLM serving much simpler:
- Purpose-built for transformer attention (PagedAttention)
- OpenAI-compatible API out of the box (no custom client needed)
- Much easier to configure and run
- Continuous batching is built in (not something you configure in Triton)

We chose vLLM because this project is purely about LLM inference and vLLM's
OpenAI-compatible API means the swap from Nebius is a single environment variable.
Triton would require writing a custom client or a conversion layer.

### Why vLLM instead of Hugging Face Text Generation Inference (TGI)?

TGI is Hugging Face's inference server — similar goals to vLLM. Both support
continuous batching and PagedAttention-style memory management. The reasons to
choose vLLM:

- vLLM has broader model support and faster updates for new architectures
- vLLM's OpenAI-compatible API is more complete (TGI has it, but vLLM's implementation
  is more mature)
- vLLM is the industry standard in 2025/2026 for self-hosted LLM serving

TGI is a fine alternative. In practice, both can serve the same models and the
performance is comparable.

---

## 6. Kubernetes — production orchestration

### What it is

Docker Compose is great for running multiple containers on **one machine**.
Kubernetes (K8s) is for running containers across a **cluster of machines** —
dozens or hundreds of servers — with automatic healing, rolling updates, and
horizontal scaling.

Kubernetes calls each running container (or group of containers) a **Pod**. A
**Deployment** says "I want 3 replicas of this Pod" and Kubernetes makes sure
there are always 3. If one crashes, Kubernetes starts a new one automatically.
A **Service** gives those Pods a stable network address. An **Ingress** routes
external HTTP traffic to Services.

### What we built

The `k8s/` directory contains:

| File | What it does |
|---|---|
| `namespace.yaml` | Creates an isolated `sentinel` namespace (like a folder for all our resources) |
| `configmap.yaml` | Environment variables for the backend (not secrets — just config) |
| `backend-pvc.yaml` | A **PersistentVolumeClaim** — requests 2 GB of storage for SQLite files |
| `backend-deployment.yaml` | Runs the backend (1 replica — see the SQLite note below) |
| `backend-service.yaml` | Gives the backend a stable internal hostname |
| `frontend-deployment.yaml` | Runs the frontend (2 replicas — stateless, so safe to scale) |
| `frontend-service.yaml` | Gives the frontend a stable internal hostname |
| `vllm-deployment.yaml` | Runs vLLM on a GPU node |
| `vllm-service.yaml` | Gives vLLM a stable internal hostname other pods can call |
| `ingress.yaml` | Routes external HTTPS traffic to backend and frontend |

To deploy to any Kubernetes cluster:
```bash
kubectl apply -f k8s/
```

### The SQLite constraint: why only 1 replica for the backend?

SQLite is a file-based database. It supports multiple readers but only one
writer at a time. If we ran 2 replicas of the backend, both would try to write
to the same SQLite file simultaneously, which would cause data corruption or
crashes.

We solved this with two settings in `backend-deployment.yaml`:
- `replicas: 1` — only ever one backend pod
- `strategy: Recreate` — when updating, kill the old pod completely before
  starting the new one (vs. `RollingUpdate`, which would briefly have 2 pods)

The comment in the manifest explains the path forward: LangGraph supports
`AsyncPostgresSaver` as a drop-in replacement for `AsyncSqliteSaver`. It's a
one-line import change. PostgreSQL supports many concurrent writers, so with
that change we could run `replicas: 10` safely.

### The vLLM K8s manifest: GPU nodes

The `vllm-deployment.yaml` contains two Kubernetes concepts for GPU access:

```yaml
nodeSelector:
  cloud.google.com/gke-accelerator: nvidia-l4
tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
```

In Kubernetes, GPU nodes are usually **tainted** — marked so that normal pods
don't accidentally land on them and waste expensive GPU capacity. Only pods that
explicitly **tolerate** the taint will be scheduled there. The `nodeSelector`
ensures the pod only runs on a GPU node, and the `toleration` allows it to
ignore the taint that would otherwise block it.

### The Ingress: special handling for SSE

The backend uses **Server-Sent Events (SSE)** — an HTTP feature where the
server keeps a connection open and streams data to the client over minutes.
Most HTTP proxies have a read timeout of 60–90 seconds, which would kill SSE
connections.

The ingress annotations fix this:
```yaml
nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"   # 1 hour
nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
nginx.ingress.kubernetes.io/proxy-buffering: "off"       # send each event immediately
```

Without these, the UI would silently drop its connection to the backend every
60 seconds and users would see stale progress indicators.

### Why Kubernetes instead of Docker Compose in production?

Docker Compose runs everything on one machine. When that machine crashes, your
service is down. Kubernetes runs across many machines so a hardware failure
doesn't take down the service. It also handles:

- **Self-healing**: crashed containers restart automatically
- **Rolling deployments**: update the app with no downtime
- **Horizontal scaling**: add more replicas under load
- **Resource limits**: prevent one service from starving others of CPU/RAM

For a portfolio project, you likely don't need K8s. But demonstrating that you
know how to write K8s manifests (especially with GPU nodes, PVCs, and SSE-aware
Ingress config) is exactly what a senior AI infrastructure role looks for.

### Why not Docker Swarm?

Docker Swarm is Docker's built-in clustering solution. It's simpler than
Kubernetes but is largely abandoned — Docker Inc. pivoted to supporting
Kubernetes instead. Kubernetes is the industry standard for container
orchestration; Swarm is a dead-end.

### Why not AWS ECS / GCP Cloud Run?

AWS Elastic Container Service (ECS) and GCP Cloud Run are managed container
platforms — no need to manage Kubernetes yourself. They're excellent choices
for production:

- Cloud Run is great for stateless services (our frontend would be perfect)
- ECS is good for services that need persistent storage

We chose to write raw Kubernetes manifests because:
1. They're portable — the same YAML works on GKE, EKS, AKS, or a self-managed cluster
2. They're more explicit about infrastructure decisions (node selectors, PVCs, taints)
3. K8s knowledge transfers to any cloud; ECS knowledge is AWS-specific

---

## 7. Fly.io — the fastest path to a real public URL

### What it is

Fly.io is a platform that takes your Dockerfile and deploys it to one of their
data centers globally, giving you a public URL (`https://your-app.fly.dev`).
It's simpler than setting up a full cloud provider (no IAM roles, no VPC config,
no load balancer setup) while still being a real server that runs your actual
container — not a serverless function.

### How to deploy

```bash
# Install the CLI:
brew install flyctl

# One-time setup:
fly auth login
fly launch --no-deploy          # reads fly.toml, creates the app
fly secrets set NEBIUS_API_KEY=sk-...
fly volumes create sentinel_data --size 2 --region ord

# Deploy:
fly deploy --dockerfile backend/Dockerfile
```

The backend will be live at `https://sentinel-api.fly.dev`.

For the frontend: deploy to **Vercel** (free, native Next.js support) with
`NEXT_PUBLIC_API=https://sentinel-api.fly.dev` set as an environment variable.
Vercel builds and hosts Next.js apps with zero configuration.

### Why Fly.io instead of AWS / GCP / Azure?

| Platform | Effort to get a public URL | Cost | Best for |
|---|---|---|---|
| Fly.io | ~10 minutes, 5 commands | Free tier available | Portfolio projects, quick demos |
| Render | ~10 minutes, UI-driven | Free tier (with sleep) | Same as Fly.io |
| Railway | ~5 minutes, UI-driven | Small monthly cost | Same as Fly.io |
| AWS EC2 + ALB | Hours (IAM, VPC, security groups, etc.) | Pay per use | Production workloads |
| GKE (GCP K8s) | Hours | Pay per use | Large-scale production |

For a portfolio project, the goal is a real URL you can link from your resume.
Fly.io achieves that in under 30 minutes. AWS is the right answer for a
production workload, but the setup overhead is not worth it for a demo.

### The `NEXT_PUBLIC_API` subtlety

Next.js variables prefixed with `NEXT_PUBLIC_` are **baked into the JavaScript
at build time**, not read at runtime. This is different from server-side
environment variables. It means you can't just set `NEXT_PUBLIC_API` when
starting the container — you have to set it when building the image. This is
why the frontend Dockerfile has a build argument:

```dockerfile
ARG NEXT_PUBLIC_API=http://localhost:8000
ENV NEXT_PUBLIC_API=$NEXT_PUBLIC_API
RUN npm run build
```

And why the Vercel deployment needs the env var set in the dashboard before
building, not after.

---

## 8. Prometheus — observability

### What it is

Prometheus is an open-source monitoring system. It works by **scraping**
(pulling) metrics from your services on a schedule (e.g., every 15 seconds).
Your service exposes a `/metrics` endpoint that returns data in a specific text
format — counters, gauges, and histograms. Prometheus stores this data and
lets you query it or send alerts when values cross thresholds.

A **counter** counts events (e.g., total HTTP requests since startup).
A **gauge** is a value that goes up and down (e.g., current in-flight requests).
A **histogram** tracks distribution of values (e.g., how many requests took
0–100ms, 100–500ms, 500ms–1s, etc.). From a histogram you can derive P50, P95, P99.

### What we added

Three lines in `backend/app/main.py`:

```python
from prometheus_fastapi_instrumentator import Instrumentator
Instrumentator().instrument(app).expose(app)
```

This automatically adds a `/metrics` endpoint to the FastAPI app. Every HTTP
endpoint gets instrumented with:
- `http_requests_total` — count of requests by method, path, and status code
- `http_request_duration_seconds` — latency histogram (gives you P50/P95/P99)
- `http_requests_in_progress` — gauge of currently active requests

### How to use it

After starting the backend:
```bash
curl http://localhost:8000/metrics
```

You'll see output like:
```
http_request_duration_seconds_bucket{le="0.005",method="GET",path="/health"} 42.0
http_request_duration_seconds_bucket{le="0.01",...} 42.0
http_requests_total{method="POST",path="/api/runs",status="200"} 7.0
```

In Kubernetes, you'd add a `ServiceMonitor` resource (if using Prometheus
Operator) or configure Prometheus to scrape the backend Service. Grafana can
then turn these metrics into dashboards.

### Why Prometheus instead of just logging?

Logs tell you what happened. Metrics tell you how the system is performing right
now. You need both:

- **Logs**: "Run abc123 failed at the assess node with error X"
- **Metrics**: "P95 latency for `POST /api/runs` has been above 2 seconds for the
  last 5 minutes" (alertable, even before anyone notices in logs)

Without metrics, you're flying blind in production. With metrics, you can set
alerts like "page me if P95 latency exceeds 5 seconds" before users start
complaining.

### Why not Datadog / New Relic / CloudWatch?

Those are managed observability platforms. They're excellent and used widely in
production. The reason to use Prometheus in a portfolio project:

- Prometheus is open-source and free
- It's the industry standard in Kubernetes environments (Prometheus Operator is
  the default monitoring stack in most K8s distributions)
- The conceptual knowledge transfers — Datadog can scrape Prometheus metrics
  too, so understanding Prometheus makes you effective with any tool

---

## 9. The latency benchmark

`scripts/latency_bench.py` measures end-to-end LLM call latency under concurrent
load. It's how you demonstrate that you understand the performance story, not
just the architecture.

```bash
pip install openai

# Baseline: measure against Nebius
python scripts/latency_bench.py \
  --url https://api.studio.nebius.com/v1/ \
  --model meta-llama/Llama-3.3-70B-Instruct \
  --api-key $NEBIUS_API_KEY \
  --concurrency 1 4 8

# Compare against local vLLM (after `docker compose --profile vllm up`):
python scripts/latency_bench.py \
  --url http://localhost:8001/v1/ \
  --model meta-llama/Meta-Llama-3.1-8B-Instruct \
  --api-key EMPTY \
  --concurrency 1 4 8
```

The output gives you P50/P95/P99 at each concurrency level. The gap between
concurrency=1 and concurrency=8 is the batching story: a well-configured
inference server (vLLM) maintains relatively flat P50 latency as concurrency
grows because it batches requests together and shares compute. A naive server
queues requests serially and P95 grows linearly with load.

---

## 10. Key architectural decisions and tradeoffs

### Decision 1: SQLite now, PostgreSQL later

**What we chose**: SQLite for the LangGraph checkpointer and event log.

**Why**: SQLite requires no external database service to set up. The entire
state lives in files on disk. For a portfolio project and a single-instance
deployment, this is perfectly adequate.

**The tradeoff**: SQLite has one writer at a time. This means we're permanently
limited to `replicas: 1` for the backend — we can't horizontally scale.

**The migration path**: LangGraph ships `AsyncPostgresSaver` as a drop-in
replacement for `AsyncSqliteSaver`. It's a one-line import change in
`backend/app/main.py`. PostgreSQL supports many concurrent writers, so after
this change we could safely run `replicas: 10`. We'd provision the database
with a managed service (AWS RDS, Google Cloud SQL) rather than running it
ourselves.

### Decision 2: Separate SQLite files for checkpointer, event log, and memory

**What we chose**: Three separate SQLite files — one for the LangGraph
checkpointer (`sentinel.db`), one for the SSE event log (`sentinel_events.db`),
one for cross-run memory (`sentinel_memory.db`).

**Why**: The LangGraph checkpointer holds a write lock for the entire duration
of a paused run (minutes or hours while waiting for human approval). If the
event log were in the same file, every attempt to write a new event would block
waiting for that lock. Separate files mean each file has exactly one writer and
they never contend.

**Alternative**: Use WAL (Write-Ahead Logging) mode in SQLite, which allows
one writer and multiple readers concurrently. We do use WAL mode, but the
contention issue is write-on-write, not write-on-read, so WAL doesn't fully
solve it. Separate files is the cleaner solution.

### Decision 3: OpenAI-compatible API everywhere

**What we chose**: Use `AsyncOpenAI(base_url=NEBIUS_BASE_URL)` rather than a
Nebius-specific SDK or a raw `httpx` call.

**Why**: The OpenAI client library and API format have become the de facto
standard for LLM inference. Nebius, vLLM, TGI, Ollama, and most other
providers implement the same API. By pointing our client at an env var rather
than hardcoding the Nebius URL, swapping providers requires zero code changes.

**The tradeoff**: We lose access to provider-specific features (Nebius might
have features not in the OpenAI API spec). In practice, for simple
chat completions this is irrelevant.

### Decision 4: vLLM profile vs always-on in Compose

**What we chose**: The `vllm` service in `docker-compose.yml` is behind a
`profiles: [vllm]` flag. It doesn't start unless you explicitly ask.

**Why**: vLLM requires an NVIDIA GPU. Most development machines don't have one.
A Compose file that tries to reserve a GPU by default would fail immediately on
most machines, making `docker compose up` broken for most users.

**Alternative**: Run two separate Compose files — one for the base stack and one
for vLLM. The `profiles` feature achieves the same result in a single file with
less duplication.

### Decision 5: Fly.io for the live URL, not AWS

**What we chose**: Fly.io for the demo deployment.

**Why**: The goal is a live URL on a resume. Fly.io achieves this in 30 minutes
with 5 commands. AWS achieves it in a few hours with ~20 steps (IAM user, ECR
repository, ECS task definition, ALB, security groups, VPC config).

**The tradeoff**: Fly.io has less flexibility than AWS. You can't customize the
network topology, add a CDN, or integrate with other AWS services. For a
production workload at a company, AWS/GCP is the right answer. For a portfolio
demo, Fly.io is strictly better.

---

## 11. What's next: Terraform and Triton

### Terraform

**Terraform** is a tool for writing your infrastructure as code. Instead of
clicking through the AWS console to create a database or a load balancer, you
write a `.tf` file that describes the desired state, and Terraform makes it
happen. More importantly, the `.tf` file is version-controlled — you can review
infrastructure changes in a pull request just like code changes.

For this project, Terraform would manage:
- The Fly.io app and volumes (Fly.io has a Terraform provider)
- A managed PostgreSQL instance (for when we migrate from SQLite)
- A GKE cluster with GPU node pools (for the vLLM deployment)

Terraform fits naturally into a CI/CD pipeline: when a PR is merged, Terraform
applies any infrastructure changes automatically, with a diff shown in the PR
review.

### Triton Inference Server

**NVIDIA Triton** is the lower-level alternative to vLLM for model serving. The
key difference: Triton is a general framework — it can serve any model format
(TensorRT, ONNX, PyTorch TorchScript, TensorFlow SavedModel). vLLM is
LLM-specific.

When would Triton be the right choice?
- You're serving an embedding model alongside the LLM (Triton can serve both)
- You need custom preprocessing pipelines (e.g., resizing images before a vision model)
- You're serving a fine-tuned model in TensorRT format for maximum GPU utilization
- You need ensemble models (chain multiple models together in one inference call)

For this project, vLLM is the right tool because:
1. We're serving only one LLM
2. The OpenAI-compatible API is a hard requirement (zero code changes from Nebius)
3. Continuous batching for LLM tokens is vLLM's core strength

A complete AI serving infrastructure story at a large company often uses both:
vLLM for the LLM inference server, Triton for embedding and vision models.

---

## 12. How all the pieces connect

```
Developer machine (local)
    ↓
  docker compose up
    ├── sentinel-backend (FastAPI + LangGraph)  → port 8000
    ├── sentinel-frontend (Next.js)             → port 3000
    └── vllm (optional, --profile vllm)         → port 8001
              ↑
         NEBIUS_BASE_URL points here instead of Nebius cloud

Production (Kubernetes cluster, e.g. GKE)
    ↓
  kubectl apply -f k8s/
    ├── Namespace: sentinel
    ├── ConfigMap: env vars for the backend
    ├── PVC: 2 GB disk for SQLite files
    ├── Deployment: sentinel-backend (1 replica, SQLite constraint)
    │     └── Service: stable hostname inside the cluster
    ├── Deployment: sentinel-frontend (2 replicas, stateless)
    │     └── Service: stable hostname inside the cluster
    ├── Deployment: vllm-inference (1 GPU node, nvidia-l4)
    │     └── Service: stable hostname → backend points NEBIUS_BASE_URL here
    └── Ingress: routes HTTPS traffic
          ├── api.sentinel.yourdomain.com → backend:8000
          └── sentinel.yourdomain.com     → frontend:3000

Quick public demo (Fly.io)
    ↓
  fly deploy
    └── sentinel-api.fly.dev (backend only)
          + Vercel frontend pointing NEXT_PUBLIC_API at Fly.io URL

Observability
    └── /metrics endpoint on the backend
          → Prometheus scrapes every 15s
          → Grafana dashboard: P50/P95/P99 latency, request rate, error rate
          → Alert: "page if P95 > 5s"
```

The benchmark script (`scripts/latency_bench.py`) works against any layer —
Nebius cloud, local vLLM via Compose, or the K8s vLLM service — because they
all speak the same OpenAI-compatible API. This is the plug-and-play advantage
of standardizing on a common interface.
