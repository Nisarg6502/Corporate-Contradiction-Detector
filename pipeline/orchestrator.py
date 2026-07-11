"""End-to-end on-demand processing for one company.

Chains the ticker-scoped pipeline stages (ingest -> extract -> graph -> index ->
detect), reporting progress via a callback, all under one Langfuse trace so every
LLM generation for the run groups together.
"""

from __future__ import annotations

from config import get_config
from observability import obs


def _noop(stage, pct, message):
    pass


def process_company(ticker: str, *, progress_cb=None, force: bool = False,
                    cfg=None) -> dict:
    ticker = str(ticker).upper()
    cfg = cfg or get_config()
    pc = cfg.processing
    cb = progress_cb or _noop

    specs = pc["filings"]
    max_chunks = int(pc.get("max_chunks_per_doc", 20))
    max_pairs = int(pc.get("max_detection_pairs", 30))

    # Imported lazily so importing the API doesn't pull heavy deps eagerly.
    from ingestion.run_ingest import ingest_company
    from extraction.run_extract import extract_documents
    from graph.run_load import load_company
    from vector.run_index import index_company
    from detection.run_detect import detect_company

    summary = {"ticker": ticker}
    with obs.run("process-company", ticker=ticker):
        cb("fetching", 5, f"Fetching {ticker} filings from SEC EDGAR…")
        doc_ids = ingest_company(ticker, specs)
        summary["documents"] = len(doc_ids)
        if not doc_ids:
            raise RuntimeError(f"No filings found for {ticker} on EDGAR.")

        cb("extracting", 25, f"Extracting claims from {len(doc_ids)} filings…")
        claims = extract_documents(doc_ids, max_chunks=max_chunks, cfg=cfg)
        summary["claims"] = len(claims)

        cb("graph", 62, "Building the knowledge graph…")
        load_company(ticker, cfg=cfg)

        cb("indexing", 76, "Indexing claims for semantic search…")
        summary["indexed"] = index_company(ticker, cfg=cfg)

        cb("detecting", 85, "Detecting contradictions…")
        confirmed = detect_company(ticker, cfg=cfg, max_pairs=max_pairs)
        summary["contradictions"] = len(confirmed)

        cb("done", 100, "Complete.")
    obs.flush()
    return summary
