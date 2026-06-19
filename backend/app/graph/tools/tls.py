"""Real TLS-expiry adapter (ADR-3: the one genuinely live discovery source).

Does an actual TLS handshake and reads ``notAfter`` from the served certificate.
Verification is disabled on purpose so we can still read the cert of an *expired*
endpoint (a verified handshake would fail before we see the cert) — we are
inspecting the cert, not trusting it. Bounded retry with backoff handles flaky
or unreachable hosts; the caller turns a failure into "unknown coverage".
"""
from __future__ import annotations

import asyncio
import socket
import ssl
from datetime import datetime, timezone
from typing import Any

from cryptography import x509


def parse_endpoint(endpoint: str, default_port: int = 443) -> tuple[str, int]:
    host, _, port = endpoint.partition(":")
    return host, int(port) if port else default_port


def _fetch_cert_der(host: str, port: int, timeout: float) -> bytes:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as ssock:
            der = ssock.getpeercert(binary_form=True)
    if not der:
        raise ssl.SSLError("no peer certificate presented")
    return der


def _not_after_utc(cert: x509.Certificate) -> datetime:
    # cryptography >= 42 exposes the tz-aware accessor; fall back for older builds.
    try:
        return cert.not_valid_after_utc
    except AttributeError:  # pragma: no cover
        return cert.not_valid_after.replace(tzinfo=timezone.utc)


async def check_tls_expiry(
    endpoint: str,
    *,
    timeout: float = 6.0,
    attempts: int = 2,
    backoff: float = 1.0,
) -> dict[str, Any]:
    """Return the real cert expiry for ``host:port``.

    On success: ``{ok: True, not_after, days_to_expiry, expired, issuer, source}``.
    On failure (after retries): ``{ok: False, error, source}``.
    """
    host, port = parse_endpoint(endpoint)
    last_err: str | None = None
    for attempt in range(1, attempts + 1):
        try:
            der = await asyncio.to_thread(_fetch_cert_der, host, port, timeout)
            cert = x509.load_der_x509_certificate(der)
            not_after = _not_after_utc(cert)
            days = (not_after - datetime.now(timezone.utc)).days
            try:
                issuer = cert.issuer.rfc4514_string()
            except Exception:
                issuer = None
            return {
                "ok": True,
                "not_after": not_after.date().isoformat(),
                "days_to_expiry": days,
                "expired": days < 0,
                "issuer": issuer,
                "source": "real_tls",
            }
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt < attempts:
                await asyncio.sleep(backoff * attempt)
    return {"ok": False, "error": last_err, "source": "real_tls"}
