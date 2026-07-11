"""Reusable read queries for sanity checks and the API (Checkpoint 6)."""

GRAPH_COUNTS = """
MATCH (n)
RETURN labels(n)[0] AS label, count(*) AS n
ORDER BY label
"""

REL_COUNTS = """
MATCH ()-[r]->()
RETURN type(r) AS rel, count(*) AS n
ORDER BY rel
"""

# Full claim timeline for one topic + company, ordered by date (the core query
# contradiction detection builds on).
CLAIMS_FOR_TOPIC = """
MATCH (co:Company {ticker: $ticker})<-[:FILED_BY]-(d:Document)<-[:APPEARS_IN]-(c:Claim)
      -[:ABOUT]->(t:Topic {id: $topic})
MATCH (s:Speaker)-[:MADE]->(c)
RETURN c.date AS date, s.name AS speaker, s.role AS role, c.source_type AS source,
       c.doc_type AS doc_type, c.stance AS stance, c.text AS claim_text,
       c.quote_span AS quote, c.claim_id AS claim_id
ORDER BY date
"""

# All confirmed contradictions for a company, filterable by min severity
# (Checkpoint 6: GET /contradictions). Returns both claims + edge metadata.
CONTRADICTIONS = """
MATCH (a:Claim)-[r:CONTRADICTS]->(b:Claim)-[:ABOUT]->(t:Topic)
MATCH (a)-[:APPEARS_IN]->(:Document)-[:FILED_BY]->(co:Company {ticker: $ticker})
MATCH (sa:Speaker)-[:MADE]->(a)
MATCH (sb:Speaker)-[:MADE]->(b)
WHERE r.severity IN $severities
RETURN t.id AS topic, t.name AS topic_name, r.severity AS severity,
       r.reasoning AS reasoning, r.judged_at AS judged_at,
       a.claim_id AS a_id, a.date AS a_date, sa.name AS a_speaker,
       a.source_type AS a_source, a.quote_span AS a_quote,
       b.claim_id AS b_id, b.date AS b_date, sb.name AS b_speaker,
       b.source_type AS b_source, b.quote_span AS b_quote
ORDER BY CASE r.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, topic
"""

TOPICS_WITH_COUNTS = """
MATCH (co:Company {ticker: $ticker})<-[:FILED_BY]-(:Document)<-[:APPEARS_IN]-(c:Claim)
      -[:ABOUT]->(t:Topic)
RETURN t.id AS topic, t.name AS name, t.description AS description,
       count(c) AS claims,
       sum(CASE c.source_type WHEN 'synthetic' THEN 1 ELSE 0 END) AS synthetic
ORDER BY claims DESC
"""
