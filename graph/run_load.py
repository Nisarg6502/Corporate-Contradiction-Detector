"""Checkpoint 4 orchestrator: schema + load claims/documents/topics into Neo4j.

    python -m graph.run_load             # setup schema + load everything
    python -m graph.run_load --reset     # wipe graph first, then load
    python -m graph.run_load --verify    # just print node/rel counts

Requires a running Neo4j (Desktop or Aura Free) with URI/password in .env.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config                       # noqa: E402
from ingestion import store                          # noqa: E402
from extraction import claim_store                   # noqa: E402
from graph import loader, queries                    # noqa: E402
from graph.connection import Neo4j                   # noqa: E402
from graph.schema import SCHEMA_STATEMENTS           # noqa: E402


def ensure_schema(db: Neo4j) -> None:
    for stmt in SCHEMA_STATEMENTS:
        db.run(stmt)


def load_company(ticker: str, *, db: Neo4j = None, cfg=None) -> dict:
    """Incrementally MERGE one company's topics/docs/claims into the graph."""
    cfg = cfg or get_config()
    close = db is None
    db = db or Neo4j(cfg)
    if close:
        db.verify()
    try:
        ensure_schema(db)
        db.write(loader.TOPICS_CYPHER, loader.topic_rows(cfg.topics))
        claims = [c for c in claim_store.load_claims().values()
                  if c.company_ticker == ticker]
        doc_ids = sorted({c.document_id for c in claims})
        docs = [store.load_document(d) for d in doc_ids]
        db.write(loader.DOCUMENTS_CYPHER, loader.document_rows(docs))
        db.write(loader.CLAIMS_CYPHER, loader.claim_rows(claims))
        return {"claims": len(claims), "documents": len(docs)}
    finally:
        if close:
            db.close()


def _print_counts(db: Neo4j) -> None:
    print("  Nodes:")
    for r in db.run(queries.GRAPH_COUNTS):
        print(f"    {r['label']:10} {r['n']}")
    print("  Relationships:")
    for r in db.run(queries.REL_COUNTS):
        print(f"    {r['rel']:14} {r['n']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete all nodes first")
    ap.add_argument("--verify", action="store_true", help="only print counts")
    args = ap.parse_args()

    cfg = get_config()
    db = Neo4j(cfg)
    db.verify()
    print(f"Connected to Neo4j at {cfg.neo4j['uri']}")

    try:
        if args.verify:
            _print_counts(db)
            return

        if args.reset:
            db.run("MATCH (n) DETACH DELETE n")
            print("Reset: all nodes deleted.")

        print("Applying schema (constraints + indexes)...")
        for stmt in SCHEMA_STATEMENTS:
            db.run(stmt)

        # Load data.
        topics = cfg.topics
        claims = list(claim_store.load_claims().values())
        doc_ids = sorted({c.document_id for c in claims})
        docs = [store.load_document(d) for d in doc_ids]

        db.write(loader.TOPICS_CYPHER, loader.topic_rows(topics))
        db.write(loader.DOCUMENTS_CYPHER, loader.document_rows(docs))
        db.write(loader.CLAIMS_CYPHER, loader.claim_rows(claims))
        print(f"Loaded {len(topics)} topics, {len(docs)} documents, {len(claims)} claims.")

        _print_counts(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
