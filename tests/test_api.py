"""Checkpoint 6 sanity checks (offline parts).

The endpoint behavior is verified live against Neo4j+Qdrant via the manual
TestClient run; these cover the DB-independent pieces so CI stays green without
live databases.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from api import deps  # noqa: E402
from extraction import claim_store  # noqa: E402


def test_severities_at_least():
    assert deps.severities_at_least("high") == ["high"]
    assert deps.severities_at_least("medium") == ["medium", "high"]
    assert deps.severities_at_least("low") == ["low", "medium", "high"]
    assert deps.severities_at_least("bogus") == ["low", "medium", "high"]


def test_citation_builder_traces_to_source():
    from api import citations
    claims = claim_store.load_claims()
    if not claims:
        pytest.skip("no extracted claims on disk")
    # A synthetic claim -> PDF render with highlight rects; real -> HTML render.
    for c in claims.values():
        cit = citations.build_citation(c.claim_id)
        assert cit["claim"]["quote_span"] == c.quote_span
        rtype = cit["render"]["type"]
        assert rtype in ("html", "pdf")
        if rtype == "html":
            # quote must be an exact substring of the rendered paragraph
            assert cit["render"]["quote_span"] in cit["render"]["paragraph_text"]
        break
