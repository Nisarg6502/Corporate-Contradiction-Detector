"""SEC company universe: search, popular, and recently-filed discovery.

Backed by SEC's public ``company_tickers.json`` (~10k companies), cached locally.
Used by the landing page so a user can find and select any public company.
"""

from __future__ import annotations

import json
import os
import urllib.request
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = PROJECT_ROOT / "data" / "company_tickers.json"
SEC_URL = "https://www.sec.gov/files/company_tickers.json"


def _user_agent() -> str:
    return os.environ.get("EDGAR_IDENTITY", "Corporate Contradiction Detector contact@example.com")


@lru_cache(maxsize=1)
def _universe() -> list[dict]:
    """List of {ticker, name, cik}, cached on disk then in memory."""
    if not CACHE_PATH.exists():
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(SEC_URL, headers={"User-Agent": _user_agent()})
        with urllib.request.urlopen(req, timeout=30) as resp:
            CACHE_PATH.write_bytes(resp.read())
    raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    rows = raw.values() if isinstance(raw, dict) else raw
    return [{"ticker": r["ticker"].upper(), "name": r["title"], "cik": int(r["cik_str"])}
            for r in rows]


@lru_cache(maxsize=1)
def _by_cik() -> dict[int, str]:
    return {c["cik"]: c["ticker"] for c in _universe()}


def search(q: str, processed: set[str] | None = None, limit: int = 15) -> list[dict]:
    q = (q or "").strip().upper()
    if not q:
        return []
    processed = processed or set()
    scored = []
    for c in _universe():
        t, name = c["ticker"], c["name"].upper()
        if t == q:
            score = 0
        elif t.startswith(q):
            score = 1
        elif q in name:
            score = 2
        elif q in t:
            score = 3
        else:
            continue
        scored.append((score, len(t), c))
    scored.sort(key=lambda s: (s[0], s[1]))
    return [{**c, "processed": c["ticker"] in processed} for _, _, c in scored[:limit]]


def resolve(tickers: list[str], processed: set[str] | None = None) -> list[dict]:
    processed = processed or set()
    idx = {c["ticker"]: c for c in _universe()}
    out = []
    for t in tickers:
        c = idx.get(t.upper())
        if c:
            out.append({**c, "processed": c["ticker"] in processed})
    return out


RECENT_CACHE = PROJECT_ROOT / "data" / "recent_filers.json"


def recent(limit: int = 12, processed: set[str] | None = None) -> list[dict]:
    """Recently-filed companies from the disk cache (cheap; never hits EDGAR here).

    The cache is populated out-of-band by ``refresh_recent`` — pulling it into the
    request path would block the single-process server (edgartools parses the full
    SEC index and holds the GIL). Returns [] if the cache is absent (UI hides it).
    """
    processed = processed or set()
    if not RECENT_CACHE.exists():
        return []
    try:
        items = json.loads(RECENT_CACHE.read_text(encoding="utf-8")).get("items", [])
    except Exception:
        return []
    return [{**it, "processed": it["ticker"] in processed} for it in items[:limit]]


def refresh_recent(limit: int = 12) -> int:
    """Heavy: pull recent 10-K/10-Q filers via edgartools and write the cache.

    Run offline (``python -m ingestion.company_universe``), NOT on the request path.
    """
    import time
    from edgar import get_filings, set_identity
    set_identity(_user_agent())
    by_cik = _by_cik()
    out, seen = [], set()
    for f in get_filings(form=["10-K", "10-Q"]).head(200):
        cik = int(getattr(f, "cik", 0) or 0)
        ticker = by_cik.get(cik)
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        out.append({"ticker": ticker, "name": getattr(f, "company", ""), "cik": cik,
                    "form": getattr(f, "form", ""), "date": str(getattr(f, "filing_date", ""))})
        if len(out) >= limit:
            break
    RECENT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    RECENT_CACHE.write_text(json.dumps({"ts": time.time(), "items": out}), encoding="utf-8")
    return len(out)


if __name__ == "__main__":
    print("Refreshed recent filers:", refresh_recent())
