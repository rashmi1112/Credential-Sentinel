"""
Latency benchmark for the Sentinel plan-node LLM call.

Measures P50 / P95 / P99 end-to-end latency under N concurrent in-flight
requests, exercising vLLM's continuous batching vs. a single-threaded baseline.

Usage:
    # Against Nebius (baseline):
    python scripts/latency_bench.py --url https://api.studio.nebius.com/v1 \
        --model meta-llama/Llama-3.3-70B-Instruct --api-key $NEBIUS_API_KEY

    # Against local vLLM (docker compose --profile vllm up):
    python scripts/latency_bench.py --url http://localhost:8001/v1 \
        --model meta-llama/Meta-Llama-3.1-8B-Instruct --api-key EMPTY \
        --concurrency 1 4 8 16

Why this matters for batching:
    vLLM uses *continuous batching* (PagedAttention paper, Kwon et al. 2023):
    new requests join the batch mid-generation instead of waiting for a full
    batch to finish. Under concurrent load the throughput advantage is large
    (often 5–10× over naive static batching) while P50 latency stays roughly
    flat up to the GPU memory limit. This script surfaces that tradeoff:
    compare P95 at concurrency=1 vs concurrency=8 to see where batching wins.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from typing import Any

from openai import AsyncOpenAI

PROMPT_FACTS: dict[str, Any] = {
    "cred_id": "bench-tls-001",
    "kind": "tls_cert",
    "days_to_expiry": 12,
    "expired": False,
    "consumers": ["api-gateway", "internal-auth"],
    "rotation_difficulty": "medium",
}

SYSTEM = (
    "You are a platform-security engineer. Draft a credential rotation plan "
    "as STRICT JSON: {\"steps\": [...], \"impact_summary\": \"...\", \"risk\": \"low|medium|high\"}. "
    "3-5 steps. No prose."
)


async def one_request(client: AsyncOpenAI, model: str) -> float:
    t0 = time.perf_counter()
    await client.chat.completions.create(
        model=model,
        temperature=0.2,
        max_tokens=300,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(PROMPT_FACTS)},
        ],
    )
    return time.perf_counter() - t0


async def run_batch(client: AsyncOpenAI, model: str, n: int) -> list[float]:
    tasks = [one_request(client, model) for _ in range(n)]
    return await asyncio.gather(*tasks)


def percentile(data: list[float], p: float) -> float:
    data = sorted(data)
    idx = (len(data) - 1) * p / 100
    lo, hi = int(idx), min(int(idx) + 1, len(data) - 1)
    return data[lo] + (data[hi] - data[lo]) * (idx - lo)


def print_stats(label: str, latencies: list[float]) -> None:
    print(f"\n  {label}")
    print(f"    n={len(latencies)}  "
          f"p50={percentile(latencies, 50):.2f}s  "
          f"p95={percentile(latencies, 95):.2f}s  "
          f"p99={percentile(latencies, 99):.2f}s  "
          f"mean={statistics.mean(latencies):.2f}s  "
          f"throughput={len(latencies)/sum(latencies)*len(latencies):.2f} req/s")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Sentinel LLM latency benchmark")
    parser.add_argument("--url", default="https://api.studio.nebius.com/v1/",
                        help="OpenAI-compatible base URL (Nebius or vLLM)")
    parser.add_argument("--model", default="meta-llama/Llama-3.3-70B-Instruct")
    parser.add_argument("--api-key", default="EMPTY",
                        help="API key ('EMPTY' works for local vLLM)")
    parser.add_argument("--concurrency", nargs="+", type=int, default=[1, 4, 8],
                        help="Concurrency levels to test (space-separated)")
    parser.add_argument("--warmup", type=int, default=2,
                        help="Warmup requests before recording")
    args = parser.parse_args()

    client = AsyncOpenAI(api_key=args.api_key, base_url=args.url, timeout=120.0)

    print(f"Benchmark: {args.url} | model={args.model}")
    print(f"Warming up with {args.warmup} request(s)...")
    await run_batch(client, args.model, args.warmup)

    for c in args.concurrency:
        # Send c requests simultaneously; this is what exercises continuous batching
        latencies = await run_batch(client, args.model, c)
        print_stats(f"concurrency={c}", latencies)

    print()


if __name__ == "__main__":
    asyncio.run(main())
