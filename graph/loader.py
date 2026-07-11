"""Pure row-builders + MERGE Cypher for loading the graph.

The row-building functions are side-effect-free (no DB), so they're unit-tested
without a live Neo4j. `run_load.py` feeds these rows to the driver via UNWIND.

Graph shape (from the plan):
  (Speaker)-[:MADE]->(Claim)-[:APPEARS_IN]->(Document)-[:FILED_BY]->(Company)
  (Claim)-[:ABOUT]->(Topic)
  (Claim)-[:CONTRADICTS]->(Claim)   # added in Checkpoint 5
"""

from __future__ import annotations


def speaker_id(ticker: str, name: str) -> str:
    return f"{ticker}::{name}"


def topic_rows(topics: list[dict]) -> list[dict]:
    return [{"id": t["id"], "name": t["name"], "description": t.get("description", "")}
            for t in topics]


def document_rows(documents: list) -> list[dict]:
    rows = []
    for d in documents:
        rows.append({
            "document_id": d.document_id,
            "doc_type": d.doc_type,
            "date": d.date,
            "period": d.period_of_report,
            "source_url": d.source_url,
            "source_type": d.source_type,
            "raw_ref": d.raw_ref,
            "ticker": d.company.get("ticker", ""),
            "company_name": d.company.get("name", ""),
            "cik": d.company.get("cik"),
        })
    return rows


def claim_rows(claims: list) -> list[dict]:
    rows = []
    for c in claims:
        rows.append({
            "claim_id": c.claim_id,
            "text": c.claim_text,
            "quote_span": c.quote_span,
            "position_anchor": c.chunk_id,       # encodes document#section#paragraph
            "section_id": c.section_id,
            "paragraph_index": c.paragraph_index,
            "value_numeric": c.value_numeric,
            "stance": c.stance,
            "date": c.date,
            "topic": c.topic,
            "speaker": c.speaker,
            "role": c.role,
            "speaker_id": speaker_id(c.company_ticker, c.speaker),
            "document_id": c.document_id,
            "source_type": c.source_type,
            "doc_type": c.doc_type,
            "ticker": c.company_ticker,
            "page": c.page,
            "bbox": c.bbox,
        })
    return rows


TOPICS_CYPHER = """
UNWIND $rows AS row
MERGE (t:Topic {id: row.id})
  SET t.name = row.name, t.description = row.description
"""

DOCUMENTS_CYPHER = """
UNWIND $rows AS row
MERGE (co:Company {ticker: row.ticker})
  ON CREATE SET co.name = row.company_name, co.cik = row.cik
MERGE (d:Document {document_id: row.document_id})
  SET d.doc_type = row.doc_type, d.date = row.date, d.period = row.period,
      d.source_url = row.source_url, d.source_type = row.source_type,
      d.raw_ref = row.raw_ref
MERGE (d)-[:FILED_BY]->(co)
"""

CLAIMS_CYPHER = """
UNWIND $rows AS row
MERGE (t:Topic {id: row.topic})
MERGE (d:Document {document_id: row.document_id})
MERGE (s:Speaker {speaker_id: row.speaker_id})
  ON CREATE SET s.name = row.speaker, s.role = row.role, s.company_ticker = row.ticker
MERGE (c:Claim {claim_id: row.claim_id})
  SET c.document_id = row.document_id, c.text = row.text, c.quote_span = row.quote_span,
      c.position_anchor = row.position_anchor, c.section_id = row.section_id,
      c.paragraph_index = row.paragraph_index, c.value_numeric = row.value_numeric,
      c.stance = row.stance, c.date = row.date, c.topic = row.topic,
      c.source_type = row.source_type, c.doc_type = row.doc_type,
      c.page = row.page, c.bbox = row.bbox
MERGE (s)-[:MADE]->(c)
MERGE (c)-[:APPEARS_IN]->(d)
MERGE (c)-[:ABOUT]->(t)
"""
