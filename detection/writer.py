"""Write confirmed CONTRADICTS edges back to the graph."""

WRITE_CONTRADICTION_CYPHER = """
UNWIND $rows AS row
MATCH (a:Claim {claim_id: row.a_id})
MATCH (b:Claim {claim_id: row.b_id})
MERGE (a)-[r:CONTRADICTS]->(b)
  SET r.severity = row.severity, r.reasoning = row.reasoning,
      r.judged_at = row.judged_at, r.judged_by = row.judged_by
"""

CLEAR_CONTRADICTIONS_CYPHER = "MATCH ()-[r:CONTRADICTS]->() DELETE r"

# Scoped clear: only this company's contradiction edges (multi-company safe).
CLEAR_CONTRADICTIONS_FOR_TICKER = """
MATCH (a:Claim)-[:APPEARS_IN]->(:Document)-[:FILED_BY]->(:Company {ticker: $ticker})
MATCH (a)-[r:CONTRADICTS]->()
DELETE r
"""
