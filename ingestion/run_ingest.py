"""Checkpoint 1 orchestrator: fetch -> parse -> store.

Run from the project root:

    python -m ingestion.run_ingest              # all filings in config/edgar.yaml
    python -m ingestion.run_ingest --one 10-K   # just the latest 10-K (sanity check)
    python -m ingestion.run_ingest --no-cache   # force re-download
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config          # noqa: E402
from ingestion import edgar_client, store  # noqa: E402
from ingestion.parser import parse_filing_html  # noqa: E402


def _parse_and_store(f):
    doc = parse_filing_html(
        f.html, document_id=f.document_id, doc_type=f.doc_type, date=f.date,
        period_of_report=f.period_of_report, source_url=f.source_url,
        source_type="real", raw_ref=f.raw_ref, company=f.company,
    )
    store.save_document(doc)
    return doc


def ingest_company(ticker: str, specs: list[dict], *, use_cache: bool = True) -> list[str]:
    """Fetch + parse + store filings for one company; return document ids."""
    from ingestion import edgar_client
    filings = edgar_client.fetch_filings_for(ticker, specs, use_cache=use_cache)
    return [_parse_and_store(f).document_id for f in filings]


def _ingest_one(f) -> None:
    doc = _parse_and_store(f)
    n_para = sum(1 for c in doc.chunks if c.chunk_type == "paragraph")
    n_tab = sum(1 for c in doc.chunks if c.chunk_type == "table")
    print(f"  {doc.doc_type:5} {doc.document_id}  {doc.date}  "
          f"sections={len(doc.sections):3d}  chunks={len(doc.chunks):4d} "
          f"(para={n_para}, table={n_tab})  -> {doc.document_id}.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", metavar="FORM", help="ingest only latest of this form")
    ap.add_argument("--no-cache", action="store_true", help="force re-download")
    args = ap.parse_args()

    cfg = get_config()
    use_cache = not args.no_cache
    print(f"Target: {cfg.edgar['target_company']['ticker']}  (cache={'on' if use_cache else 'off'})")

    if args.one:
        filings = [edgar_client.fetch_latest(cfg, form=args.one, use_cache=use_cache)]
    else:
        filings = edgar_client.fetch_filings(cfg, use_cache=use_cache)

    print(f"Fetched {len(filings)} filing(s). Parsing...")
    for f in filings:
        _ingest_one(f)
    print(f"Done. Intermediate store: {store.PROCESSED_DIR}")


if __name__ == "__main__":
    main()
