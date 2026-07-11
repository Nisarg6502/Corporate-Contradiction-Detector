"""EDGAR fetch layer (edgartools).

Resolves the target company + filing selection from config, downloads filing
HTML (caching raw bytes to ``data/raw`` so re-parses are byte-stable), and
returns lightweight metadata for the parser. No LLM here — pure fetch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from edgar import Company, set_identity

from . import store


@dataclass
class FetchedFiling:
    document_id: str      # accession number
    doc_type: str         # form, e.g. "10-K"
    date: str             # filing date (ISO)
    period_of_report: str | None
    source_url: str
    company: dict         # {ticker, cik, name}
    html: str
    raw_ref: str          # path to cached raw HTML


def _ensure_identity() -> None:
    identity = os.environ.get("EDGAR_IDENTITY")
    if not identity:
        raise RuntimeError(
            "EDGAR_IDENTITY is not set. The SEC requires a descriptive "
            "User-Agent (e.g. 'Your Name you@example.com'). Add it to .env."
        )
    set_identity(identity)


def fetch_filings_for(ticker: str, specs: list[dict], *,
                      use_cache: bool = True) -> list[FetchedFiling]:
    """Fetch the filings in ``specs`` (list of {form, limit}) for ``ticker``."""
    _ensure_identity()
    company = Company(ticker)
    company_meta = {"ticker": str(ticker).upper(), "cik": int(company.cik),
                    "name": company.name}
    results: list[FetchedFiling] = []
    for spec in specs:
        form, limit = spec["form"], int(spec.get("limit", 1))
        filings = company.get_filings(form=form).head(limit)
        for filing in filings:
            results.append(_to_fetched(filing, form, company_meta, use_cache))
    return results


def fetch_filings(cfg, *, use_cache: bool = True) -> list[FetchedFiling]:
    """Fetch the filings described by ``cfg.edgar`` for the target company."""
    ec = cfg.edgar
    return fetch_filings_for(ec["target_company"]["ticker"], ec["filings"]["types"],
                             use_cache=use_cache)


def fetch_latest(cfg, form: str = "10-K", *, use_cache: bool = True) -> FetchedFiling:
    """Fetch a single latest filing of ``form`` — used by the sanity check."""
    _ensure_identity()
    ticker = cfg.edgar["target_company"]["ticker"]
    company = Company(ticker)
    company_meta = {"ticker": ticker, "cik": int(company.cik), "name": company.name}
    filing = company.get_filings(form=form).latest(1)
    return _to_fetched(filing, form, company_meta, use_cache)


def _to_fetched(filing, form: str, company_meta: dict,
                use_cache: bool) -> FetchedFiling:
    document_id = filing.accession_no
    html = store.load_raw_html(document_id) if use_cache else None
    if html is None:
        html = filing.html()
        raw_path = store.save_raw_html(document_id, html)
    else:
        raw_path = store.RAW_DIR / f"{document_id.replace('/', '_')}.html"

    source_url = getattr(filing, "filing_url", None) or getattr(filing, "url", "")
    period = getattr(filing, "period_of_report", None)
    return FetchedFiling(
        document_id=document_id,
        doc_type=form,
        date=str(filing.filing_date),
        period_of_report=str(period) if period else None,
        source_url=source_url,
        company=company_meta,
        html=html,
        raw_ref=str(raw_path),
    )
