"""Candidate contradiction-pair generation.

Graph traversal narrows the search: pairs of claims on the SAME topic + company
from DIFFERENT documents. Prioritization puts cross-source pairs (synthetic
earnings-call vs real filing) first — that's where planted contradictions live —
and caps the count so the (more expensive) LLM judgment pass stays small.
"""

from __future__ import annotations

# Same topic + company, different documents, deduped (a<b).
CANDIDATE_PAIRS_CYPHER = """
MATCH (co:Company {ticker: $ticker})<-[:FILED_BY]-(da:Document)<-[:APPEARS_IN]-(a:Claim)
      -[:ABOUT]->(t:Topic)<-[:ABOUT]-(b:Claim)-[:APPEARS_IN]->(db:Document)-[:FILED_BY]->(co)
MATCH (sa:Speaker)-[:MADE]->(a)
MATCH (sb:Speaker)-[:MADE]->(b)
WHERE a.claim_id < b.claim_id AND da.document_id <> db.document_id
RETURN t.id AS topic,
       a.claim_id AS a_id, a.date AS a_date, sa.name AS a_speaker,
       a.source_type AS a_source, a.doc_type AS a_doctype, da.period AS a_period,
       a.quote_span AS a_quote,
       b.claim_id AS b_id, b.date AS b_date, sb.name AS b_speaker,
       b.source_type AS b_source, b.doc_type AS b_doctype, db.period AS b_period,
       b.quote_span AS b_quote
"""


def prioritize(rows: list[dict], *, max_pairs: int = 40,
               cross_source_only: bool = True) -> list[dict]:
    """Order + cap candidate pairs. Cross-source pairs first."""
    def is_cross(r):
        return r["a_source"] != r["b_source"]

    rows = list(rows)
    if cross_source_only:
        rows = [r for r in rows if is_cross(r)]
    # Cross-source first, then group by topic for readable review.
    rows.sort(key=lambda r: (not is_cross(r), r["topic"]))
    return rows[:max_pairs]
