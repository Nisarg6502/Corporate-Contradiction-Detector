"""Persistence for extracted claims (JSON), keyed by deterministic claim_id."""

from __future__ import annotations

import json
from pathlib import Path

from .schema import Claim

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLAIMS_PATH = PROJECT_ROOT / "data" / "processed" / "claims.json"


def load_claims() -> dict[str, Claim]:
    if not CLAIMS_PATH.exists():
        return {}
    data = json.loads(CLAIMS_PATH.read_text(encoding="utf-8"))
    return {cid: Claim.from_dict(c) for cid, c in data.items()}


def save_claims(claims: dict[str, Claim]) -> Path:
    CLAIMS_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {cid: c.to_dict() for cid, c in claims.items()}
    CLAIMS_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return CLAIMS_PATH


def upsert(new_claims: list[Claim]) -> dict[str, Claim]:
    store = load_claims()
    for c in new_claims:
        store[c.claim_id] = c
    save_claims(store)
    return store
