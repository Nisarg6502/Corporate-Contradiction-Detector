"""Checkpoint 4 sanity checks: graph row-builders (no live Neo4j needed).

The DB write is thin UNWIND Cypher; the logic worth testing is the mapping from
Claim/Document objects to parameter rows, which these cover without a database.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extraction.schema import Claim  # noqa: E402
from graph import loader  # noqa: E402
from graph.schema import SCHEMA_STATEMENTS  # noqa: E402
from ingestion.models import Document  # noqa: E402


def _claim(**kw):
    base = dict(claim_id="c1", document_id="D1", chunk_id="D1#s003#p5",
                section_id="s003", paragraph_index=5, topic="supply_chain_risk",
                speaker="Jensen Huang", role="CEO", claim_text="supply concentrated",
                quote_span="supply chain is mainly concentrated in Asia",
                stance="concentration risk", value_numeric=None, date="2026-02-25",
                source_type="real", doc_type="10-K", company_ticker="NVDA",
                page=None, bbox=None)
    base.update(kw)
    return Claim(**base)


def test_speaker_id_scopes_by_company():
    assert loader.speaker_id("NVDA", "Jensen Huang") == "NVDA::Jensen Huang"
    assert loader.speaker_id("NVDA", "Company") == "NVDA::Company"


def test_claim_row_carries_anchor_and_speaker_id():
    row = loader.claim_rows([_claim()])[0]
    assert row["position_anchor"] == "D1#s003#p5"
    assert row["section_id"] == "s003" and row["paragraph_index"] == 5
    assert row["speaker_id"] == "NVDA::Jensen Huang"
    assert row["quote_span"].startswith("supply chain")


def test_synthetic_claim_row_keeps_page_bbox():
    row = loader.claim_rows([_claim(source_type="synthetic", doc_type="earnings_call",
                                    page=1, bbox=[72.0, 100.0, 500.0, 130.0])])[0]
    assert row["page"] == 1 and row["bbox"][0] == 72.0


def test_document_rows_expose_company():
    doc = Document(document_id="D1", doc_type="10-K", date="2026-02-25",
                   period_of_report=None, source_url="http://x", source_type="real",
                   raw_ref="x.html", company={"ticker": "NVDA", "name": "NVIDIA CORP",
                                              "cik": 1045810}, parsed_at="")
    row = loader.document_rows([doc])[0]
    assert row["ticker"] == "NVDA" and row["company_name"] == "NVIDIA CORP"
    assert row["cik"] == 1045810


def test_schema_has_unique_constraints_for_every_node_key():
    joined = " ".join(SCHEMA_STATEMENTS)
    for key in ["c.ticker IS UNIQUE", "t.id IS UNIQUE", "d.document_id IS UNIQUE",
                "c.claim_id IS UNIQUE", "s.speaker_id IS UNIQUE"]:
        assert key in joined


def test_cypher_defines_expected_relationships():
    assert "[:MADE]->" in loader.CLAIMS_CYPHER
    assert "[:APPEARS_IN]->" in loader.CLAIMS_CYPHER
    assert "[:ABOUT]->" in loader.CLAIMS_CYPHER
    assert "[:FILED_BY]->" in loader.DOCUMENTS_CYPHER
