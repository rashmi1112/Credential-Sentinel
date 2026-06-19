"""Prove the real TLS adapter reads notAfter from live endpoints."""
import asyncio

from app.graph.tools.tls import check_tls_expiry


async def main():
    for ep in ("expired.badssl.com:443", "badssl.com:443", "nonexistent.invalid:443"):
        res = await check_tls_expiry(ep, attempts=2, timeout=6.0)
        print(ep, "->", res)


asyncio.run(main())
