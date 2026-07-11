"""FastAPI backend for the Corporate Contradiction Detector (Checkpoint 6).

Endpoints:
  GET /companies
  GET /companies/{ticker}/topics
  GET /topics/{topic_id}/claims?ticker=
  GET /contradictions?ticker=&min_severity=
  GET /claims/{id}/citation
  GET /claims/{id}/page.png        (synthetic page image for the citation viewer)
  GET /search?q=&ticker=           (hybrid: Qdrant relevance + graph context)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Query        # noqa: E402
from fastapi.middleware.cors import CORSMiddleware        # noqa: E402
from fastapi.responses import Response                    # noqa: E402

from api import citations, deps, jobs                      # noqa: E402
from graph import queries                                  # noqa: E402
from ingestion import company_universe                     # noqa: E402

app = FastAPI(title="Corporate Contradiction Detector API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/companies")
def companies():
    q = """
    MATCH (co:Company)
    OPTIONAL MATCH (co)<-[:FILED_BY]-(d:Document)
    OPTIONAL MATCH (d)<-[:APPEARS_IN]-(c:Claim)
    RETURN co.ticker AS ticker, co.name AS name, co.cik AS cik,
           count(DISTINCT d) AS documents, count(DISTINCT c) AS claims
    ORDER BY ticker
    """
    return [dict(r) for r in deps.neo4j().run(q)]


def _processed_tickers() -> set:
    return {r["ticker"] for r in deps.neo4j().run("MATCH (co:Company) RETURN co.ticker AS ticker")}


@app.get("/company-search")
def company_search(q: str = Query(...)):
    return company_universe.search(q, processed=_processed_tickers())


@app.get("/company-search/popular")
def company_popular():
    tickers = deps.cfg().processing.get("popular", [])
    return company_universe.resolve(tickers, processed=_processed_tickers())


@app.get("/company-search/recent")
def company_recent():
    return company_universe.recent(processed=_processed_tickers())


@app.post("/companies/{ticker}/process")
def process_company(ticker: str, force: bool = False):
    ticker = ticker.upper()
    if not force and ticker in _processed_tickers():
        return {"status": "done", "ticker": ticker, "already_processed": True}
    return jobs.start_processing(ticker, force=force)


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    j = jobs.get_job(job_id)
    if j is None:
        raise HTTPException(404, f"job {job_id} not found")
    return j


@app.get("/companies/{ticker}/topics")
def company_topics(ticker: str):
    rows = deps.neo4j().run(queries.TOPICS_WITH_COUNTS, ticker=ticker)
    return [dict(r) for r in rows]


@app.get("/topics/{topic_id}/claims")
def topic_claims(topic_id: str, ticker: str = Query(...)):
    rows = deps.neo4j().run(queries.CLAIMS_FOR_TOPIC, ticker=ticker, topic=topic_id)
    return [dict(r) for r in rows]


@app.get("/contradictions")
def contradictions(ticker: str = Query(...), min_severity: str = "low"):
    sevs = deps.severities_at_least(min_severity)
    rows = deps.neo4j().run(queries.CONTRADICTIONS, ticker=ticker, severities=sevs)
    return [dict(r) for r in rows]


@app.get("/claims/{claim_id}/citation")
def claim_citation(claim_id: str):
    cit = citations.build_citation(claim_id)
    if cit is None:
        raise HTTPException(404, f"claim {claim_id} not found")
    return cit


@app.get("/claims/{claim_id}/page.png")
def claim_page_image(claim_id: str):
    cit = citations.build_citation(claim_id)
    if cit is None or cit["render"]["type"] != "pdf":
        raise HTTPException(404, "no page image for this claim")
    from ingestion import pdf_parser
    png = pdf_parser.render_page_png(cit["render"]["pdf_ref"], cit["render"]["page"], dpi=150)
    return Response(content=png, media_type="image/png")


@app.get("/search")
def search(q: str = Query(...), ticker: str | None = None, limit: int = 10):
    from vector import embedder, qdrant_store
    vec = embedder.embed_one(q)
    coll = deps.cfg().qdrant["claim_collection"]
    hits = qdrant_store.search(deps.qdrant(), coll, vec, limit=limit, ticker=ticker)
    # Graph enrichment: which hits participate in a contradiction, with whom.
    ids = [h["claim_id"] for h in hits]
    enrich = {}
    if ids:
        rows = deps.neo4j().run(
            """
            MATCH (c:Claim)-[r:CONTRADICTS]-(o:Claim)
            WHERE c.claim_id IN $ids
            RETURN c.claim_id AS claim_id,
                   collect({partner: o.claim_id, severity: r.severity})[0..5] AS conflicts
            """, ids=ids)
        enrich = {r["claim_id"]: r["conflicts"] for r in rows}
    for h in hits:
        h["contradictions"] = enrich.get(h["claim_id"], [])
    return {"query": q, "results": hits}
