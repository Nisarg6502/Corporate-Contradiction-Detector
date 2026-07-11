"""Checkpoint 3 orchestrator: extract claims from stored documents.

    python -m extraction.run_extract                 # synthetic + latest 10-K (capped)
    python -m extraction.run_extract --all           # every stored document
    python -m extraction.run_extract --synthetic-only
    python -m extraction.run_extract --dry-run       # no API calls; show chunk plan

Writes/updates data/processed/claims.json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config                       # noqa: E402
from ingestion import store                          # noqa: E402
from extraction import claim_store                   # noqa: E402
from extraction.providers import make_llm_call  # noqa: E402
from extraction.extractor import extract_claims_for_chunk  # noqa: E402
from extraction.relevance import select_chunks       # noqa: E402


def extract_documents(doc_ids: list[str], *, max_chunks: int | None = None,
                      cfg=None) -> list:
    """Extract + upsert claims for the given documents; return the claims."""
    cfg = cfg or get_config()
    topics = cfg.topics
    llm_call = make_llm_call(cfg)
    max_retries = int(cfg.models["extraction"].get("max_quote_span_retries", 2))
    all_claims = []
    for did in doc_ids:
        doc = store.load_document(did)
        for ch in select_chunks(doc, topics, max_chunks=max_chunks):
            try:
                all_claims += extract_claims_for_chunk(
                    ch, doc, llm_call=llm_call, topics=topics,
                    max_retries=max_retries, model_name=llm_call.model)
            except Exception as e:  # a transient LLM error on one chunk shouldn't
                print(f"  [skip chunk {ch.chunk_id}] {type(e).__name__}: {str(e)[:120]}")
    claim_store.upsert(all_claims)
    return all_claims


def _pick_documents(index: dict, args) -> list[str]:
    syn = [d for d in index if index[d]["source_type"] == "synthetic"]
    if args.synthetic_only:
        return sorted(syn)
    if args.all:
        return list(index)
    # Default: synthetic + the single latest 10-K.
    tenks = [d for d in index if index[d]["doc_type"] == "10-K"]
    tenks.sort(key=lambda d: index[d]["date"], reverse=True)
    return sorted(syn) + tenks[:1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--synthetic-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="no API calls")
    ap.add_argument("--max-chunks", type=int, default=40,
                    help="cap chunks per filing (default 40)")
    ap.add_argument("--contains", action="append", default=[],
                    help="only extract chunks containing this phrase (repeatable); "
                         "targets specific demo-critical sections")
    args = ap.parse_args()

    cfg = get_config()
    topics = cfg.topics
    index = store.list_documents()
    doc_ids = _pick_documents(index, args)
    print(f"Documents to process: {len(doc_ids)}")

    # Plan chunks first (works without an API key).
    plan = []
    for did in doc_ids:
        doc = store.load_document(did)
        if args.contains:
            phrases = [p.lower() for p in args.contains]
            chunks = [c for c in doc.chunks
                      if c.chunk_type in ("paragraph", "table")
                      and any(p in c.text.lower() for p in phrases)]
        else:
            chunks = select_chunks(doc, topics, max_chunks=args.max_chunks)
        plan.append((doc, chunks))
        print(f"  {doc.document_id:28} {doc.source_type:9} chunks_selected={len(chunks)}")
    total = sum(len(c) for _, c in plan)
    print(f"Total chunks to extract from: {total}")

    if args.dry_run:
        print("Dry run — no API calls made.")
        return

    llm_call = make_llm_call(cfg)
    max_retries = int(cfg.models["extraction"].get("max_quote_span_retries", 2))
    all_claims = []
    for doc, chunks in plan:
        doc_claims = []
        for ch in chunks:
            doc_claims += extract_claims_for_chunk(
                ch, doc, llm_call=llm_call, topics=topics,
                max_retries=max_retries, model_name=llm_call.model)
        all_claims += doc_claims
        print(f"  {doc.document_id:28} -> {len(doc_claims)} claims")

    claim_store.upsert(all_claims)
    print(f"Extracted {len(all_claims)} claims -> {claim_store.CLAIMS_PATH}")


if __name__ == "__main__":
    main()
