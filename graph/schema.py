"""Neo4j schema: uniqueness constraints + lookup indexes.

Single-property uniqueness constraints only (composite node-key constraints are
Enterprise/Aura-tier), so every node type gets a synthetic unique key:
Company.ticker, Topic.id, Document.document_id, Claim.claim_id,
Speaker.speaker_id (= "<ticker>::<name>").
"""

SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT company_ticker IF NOT EXISTS "
    "FOR (c:Company) REQUIRE c.ticker IS UNIQUE",
    "CREATE CONSTRAINT topic_id IF NOT EXISTS "
    "FOR (t:Topic) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT document_id IF NOT EXISTS "
    "FOR (d:Document) REQUIRE d.document_id IS UNIQUE",
    "CREATE CONSTRAINT claim_id IF NOT EXISTS "
    "FOR (c:Claim) REQUIRE c.claim_id IS UNIQUE",
    "CREATE CONSTRAINT speaker_id IF NOT EXISTS "
    "FOR (s:Speaker) REQUIRE s.speaker_id IS UNIQUE",
    # Lookup indexes (plan: index Company/Speaker/Topic name).
    "CREATE INDEX topic_name IF NOT EXISTS FOR (t:Topic) ON (t.name)",
    "CREATE INDEX speaker_name IF NOT EXISTS FOR (s:Speaker) ON (s.name)",
    "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
    "CREATE INDEX claim_topic IF NOT EXISTS FOR (c:Claim) ON (c.topic)",
]
