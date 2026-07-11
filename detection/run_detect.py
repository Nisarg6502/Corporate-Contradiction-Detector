"""Checkpoint 5 orchestrator: candidate pairs -> LLM judgment -> CONTRADICTS edges.

    python -m detection.run_detect                 # NVDA, cross-source pairs
    python -m detection.run_detect --all-pairs     # also same-source pairs
    python -m detection.run_detect --dry-run       # list candidates, no LLM

Writes CONTRADICTS relationships for confirmed contradictions and prints them
for manual review.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config                       # noqa: E402
from detection import candidates, judge, writer      # noqa: E402
from graph.connection import Neo4j                   # noqa: E402

_SEV_ORDER = {"high": 0, "medium": 1, "low": 2}


def detect_company(ticker: str, *, cfg=None, max_pairs: int = 40,
                   db=None) -> list[dict]:
    """Detect + write contradictions for one company.

    Auto-selects mode: companies with synthetic transcripts (NVDA) use
    cross-source pairs; companies with only real filings use all cross-document
    pairs (real cross-time detection). Contradiction edges are cleared per-ticker
    so other companies are unaffected.
    """
    cfg = cfg or get_config()
    close = db is None
    db = db or Neo4j(cfg)
    if close:
        db.verify()
    try:
        rows = [dict(r) for r in db.run(candidates.CANDIDATE_PAIRS_CYPHER, ticker=ticker)]
        has_synth = any(r["a_source"] == "synthetic" or r["b_source"] == "synthetic"
                        for r in rows)
        pairs = candidates.prioritize(rows, max_pairs=max_pairs,
                                      cross_source_only=has_synth)
        judge_call = judge.build_judge_call(cfg)
        now = datetime.now(timezone.utc).isoformat()
        confirmed = []
        for p in pairs:
            try:
                v = judge_call(p)
            except Exception as e:  # skip a pair that errors; don't fail the run
                print(f"  [skip pair] {type(e).__name__}: {str(e)[:120]}")
                continue
            if v["contradicts"] and v["severity"] in ("low", "medium", "high"):
                confirmed.append({
                    "a_id": p["a_id"], "b_id": p["b_id"], "topic": p["topic"],
                    "severity": v["severity"], "reasoning": v["reasoning"],
                    "judged_at": now, "judged_by": judge_call.model, "_pair": p,
                })
        db.run(writer.CLEAR_CONTRADICTIONS_FOR_TICKER, ticker=ticker)
        if confirmed:
            db.write(writer.WRITE_CONTRADICTION_CYPHER,
                     [{k: v for k, v in c.items() if k != "_pair"} for c in confirmed])
        confirmed.sort(key=lambda c: _SEV_ORDER.get(c["severity"], 9))
        return confirmed
    finally:
        if close:
            db.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", default=None)
    ap.add_argument("--max-pairs", type=int, default=40)
    ap.add_argument("--all-pairs", action="store_true",
                    help="include same-source pairs (default: cross-source only)")
    ap.add_argument("--dry-run", action="store_true", help="list candidates, no LLM")
    args = ap.parse_args()

    cfg = get_config()
    ticker = args.ticker or cfg.edgar["target_company"]["ticker"]
    db = Neo4j(cfg)
    db.verify()

    try:
        rows = [dict(r) for r in db.run(candidates.CANDIDATE_PAIRS_CYPHER, ticker=ticker)]
        pairs = candidates.prioritize(rows, max_pairs=args.max_pairs,
                                      cross_source_only=not args.all_pairs)
        print(f"Candidate pairs: {len(pairs)} (of {len(rows)} same-topic pairs)")
        if args.dry_run:
            for p in pairs:
                print(f"  [{p['topic']}] {p['a_source']} vs {p['b_source']}")
            return

        judge_call = judge.build_judge_call(cfg)
        now = datetime.now(timezone.utc).isoformat()
        confirmed = []
        for p in pairs:
            verdict = judge_call(p)
            if verdict["contradicts"] and verdict["severity"] in ("low", "medium", "high"):
                confirmed.append({
                    "a_id": p["a_id"], "b_id": p["b_id"], "topic": p["topic"],
                    "severity": verdict["severity"], "reasoning": verdict["reasoning"],
                    "judged_at": now, "judged_by": judge_call.model,
                    "_pair": p,
                })

        # Idempotent: clear prior edges, then write the current confirmed set.
        db.run(writer.CLEAR_CONTRADICTIONS_CYPHER)
        if confirmed:
            db.write(writer.WRITE_CONTRADICTION_CYPHER,
                     [{k: v for k, v in c.items() if k != "_pair"} for c in confirmed])

        confirmed.sort(key=lambda c: _SEV_ORDER.get(c["severity"], 9))
        print(f"\n=== CONFIRMED CONTRADICTIONS: {len(confirmed)} ===")
        for c in confirmed:
            p = c["_pair"]
            print(f"\n[{c['severity'].upper()}] topic={c['topic']}")
            print(f"  A ({p['a_source']} {p['a_date']}, {p['a_speaker']}): {p['a_quote'][:100]!r}")
            print(f"  B ({p['b_source']} {p['b_date']}, {p['b_speaker']}): {p['b_quote'][:100]!r}")
            print(f"  reasoning: {c['reasoning']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
