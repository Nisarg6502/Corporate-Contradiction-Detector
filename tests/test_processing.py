"""Tests for company search ranking + the background job registry (offline)."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion import company_universe  # noqa: E402
from api import jobs  # noqa: E402

FIXTURE = [
    {"ticker": "AAPL", "name": "Apple Inc.", "cik": 320193},
    {"ticker": "AMZN", "name": "Amazon Com Inc", "cik": 1018724},
    {"ticker": "GOOGL", "name": "Alphabet Inc.", "cik": 1652044},
    {"ticker": "NVDA", "name": "NVIDIA Corp", "cik": 1045810},
]


def test_search_ranks_exact_ticker_first(monkeypatch):
    monkeypatch.setattr(company_universe, "_universe", lambda: FIXTURE)
    out = company_universe.search("AAPL", processed={"NVDA"})
    assert out[0]["ticker"] == "AAPL"
    assert all("processed" in r for r in out)


def test_search_matches_name_and_prefix(monkeypatch):
    monkeypatch.setattr(company_universe, "_universe", lambda: FIXTURE)
    tickers = [r["ticker"] for r in company_universe.search("A")]
    assert "AAPL" in tickers and "AMZN" in tickers          # ticker prefix
    assert "GOOGL" in tickers                                # "Alphabet" name contains A
    out = company_universe.search("alphabet")
    assert out and out[0]["ticker"] == "GOOGL"


def test_search_marks_processed(monkeypatch):
    monkeypatch.setattr(company_universe, "_universe", lambda: FIXTURE)
    out = company_universe.search("NVDA", processed={"NVDA"})
    assert out[0]["processed"] is True


def test_job_registry_runs_and_completes(monkeypatch):
    calls = []

    def fake_process(ticker, *, progress_cb=None, force=False, cfg=None):
        progress_cb("fetching", 5, "f")
        progress_cb("detecting", 85, "d")
        calls.append(ticker)
        return {"ticker": ticker, "claims": 3, "contradictions": 1}

    import pipeline.orchestrator as orch
    monkeypatch.setattr(orch, "process_company", fake_process)

    job = jobs.start_processing("aapl")
    assert job["ticker"] == "AAPL"
    assert job["status"] in ("queued", "running", "done")

    for _ in range(50):
        j = jobs.get_job(job["job_id"])
        if j["status"] in ("done", "error"):
            break
        time.sleep(0.05)

    j = jobs.get_job(job["job_id"])
    assert j["status"] == "done", j
    assert j["progress"] == 100 and j["summary"]["claims"] == 3
    assert calls == ["AAPL"]
