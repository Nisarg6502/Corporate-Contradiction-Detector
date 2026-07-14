"""Bounded retry with exponential backoff for flaky external calls.

A processing run makes many network calls to services that fail *transiently* —
Ollama Cloud's free tier times out / 503s under load, SEC EDGAR rate-limits, and
the managed DBs blip. Without retries, one transient error aborts a multi-minute
job. `with_retry` re-runs a call a **small, bounded** number of times (never
infinite — a genuinely broken call must still surface quickly) with exponential
backoff + jitter.

Only *transient-looking* errors are retried (see `_TRANSIENT_HINTS`); everything
else — bad input, auth failures, programming errors — raises on the first try so
retries don't mask real bugs or waste the free-tier quota. Matching is by
exception type/message substring rather than importing every client's exception
classes (ollama, httpx, neo4j, qdrant), which keeps this a zero-dependency leaf
(lives in `observability` only because that package is already a cross-cutting
leaf imported everywhere; it has nothing to do with tracing).
"""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")

# Substrings (lowercased) that mark an error as worth retrying: network/timeout
# blips, transient 5xx/429s, and free-tier "overloaded" responses.
_TRANSIENT_HINTS = (
    "timeout", "timed out", "connection", "connectionerror", "connect error",
    "temporarily", "unavailable", "reset by peer", "broken pipe", "eof",
    "rate limit", "ratelimit", "overloaded", "too many requests",
    "502", "503", "504", "429", "read timed out", "remote end closed",
)


def is_transient(exc: BaseException) -> bool:
    """True if `exc` looks like a transient network/service error worth retrying."""
    msg = f"{type(exc).__name__}: {exc}".lower()
    return any(hint in msg for hint in _TRANSIENT_HINTS)


def with_retry(
    fn: Callable[..., T],
    *args,
    attempts: int = 3,
    base_delay: float = 1.5,
    max_delay: float = 20.0,
    label: str = "call",
    retry_on: Callable[[BaseException], bool] = is_transient,
    **kwargs,
) -> T:
    """Call ``fn(*args, **kwargs)``, retrying transient failures up to ``attempts``
    times with exponential backoff + jitter. Non-transient errors (per
    ``retry_on``) and the final attempt re-raise immediately."""
    last_exc: BaseException | None = None
    for i in range(1, attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — deliberately broad; re-raised below
            last_exc = exc
            if i >= attempts or not retry_on(exc):
                raise
            delay = min(max_delay, base_delay * (2 ** (i - 1)))
            delay += random.uniform(0, delay * 0.25)  # jitter to de-sync retries
            # Best-effort breadcrumb (shows up in Cloud Run logs); never let a
            # logging error mask the real failure we're retrying.
            try:
                print(f"[retry] {label}: attempt {i}/{attempts} failed "
                      f"({type(exc).__name__}: {exc}); retrying in {delay:.1f}s",
                      flush=True)
            except Exception:
                pass
            time.sleep(delay)
    assert last_exc is not None  # unreachable: loop either returns or raises
    raise last_exc
