"""Ticker-locked retrieval tools for the chatbot's orchestrator agent.

Every tool is a closure over one `ticker`, baked in by `make_tools(ticker)` —
the model never supplies a ticker as an argument, so it cannot query another
company's data no matter what it's asked or told to do. This is the chatbot's
primary guardrail (see chatbot/guardrails.py for the input/output layers).

Each tool uses `response_format="content_and_artifact"`: `content` is the
compact text the LLM reads, `artifact` is the raw row data (carrying
`claim_id`s) the graph uses to track what was actually retrieved this turn,
for the output guardrail's grounding check. Tools reuse the existing
retrieval layer verbatim — no new queries beyond `list_speakers` and the
`get_citation` ownership check, both following the same patterns already in
`graph/queries.py` / `api/app.py`.
"""

from __future__ import annotations

from langchain_core.tools import tool

from api import citations, deps
from graph import queries

_SPEAKERS_FOR_TICKER = """
MATCH (co:Company {ticker: $ticker})<-[:FILED_BY]-(:Document)<-[:APPEARS_IN]-(c:Claim)
MATCH (s:Speaker)-[:MADE]->(c)
RETURN s.name AS speaker, s.role AS role, count(c) AS claims
ORDER BY claims DESC
"""

_CLAIM_BELONGS_TO_TICKER = """
MATCH (c:Claim {claim_id: $claim_id})-[:APPEARS_IN]->(:Document)-[:FILED_BY]->(co:Company {ticker: $ticker})
RETURN count(c) > 0 AS ok
"""


def _source_tag(source_type: str) -> str:
    return "SYNTHETIC DEMO DATA" if source_type == "synthetic" else "real filing"


def make_tools(ticker: str) -> list:
    """Build the retrieval tool set for one chat session, scoped to `ticker`."""

    @tool(response_format="content_and_artifact")
    def list_topics() -> tuple[str, list[dict]]:
        """List every topic this company has claims about, with claim counts
        and how many (if any) are from the synthetic demo corpus. Call this
        first to see what's available before drilling into a specific topic."""
        rows = [dict(r) for r in deps.neo4j().run(queries.TOPICS_WITH_COUNTS, ticker=ticker)]
        if not rows:
            return "No topics found for this company.", []
        lines = [
            f"- {r['topic']} ({r['name']}): {r['claims']} claims"
            + (f", {r['synthetic']} synthetic" if r["synthetic"] else "")
            for r in rows
        ]
        return "\n".join(lines), rows

    @tool(response_format="content_and_artifact")
    def get_claim_timeline(topic_id: str) -> tuple[str, list[dict]]:
        """Get every claim this company has made about one topic, ordered by
        date, with the speaker, source document, and verbatim quote for each.
        `topic_id` must be one of the ids returned by list_topics (e.g.
        'gross_margin_profitability')."""
        rows = [dict(r) for r in deps.neo4j().run(
            queries.CLAIMS_FOR_TOPIC, ticker=ticker, topic=topic_id)]
        if not rows:
            return f"No claims found for topic '{topic_id}'.", []
        lines = [
            f"[{r['claim_id']}] {r['date']} — {r['speaker']} ({r['role'] or 'n/a'}), "
            f"{r['doc_type']} [{_source_tag(r['source'])}]: \"{r['quote']}\" "
            f"(stance: {r['stance']})"
            for r in rows
        ]
        return "\n".join(lines), rows

    @tool(response_format="content_and_artifact")
    def get_contradictions(min_severity: str = "low") -> tuple[str, list[dict]]:
        """Get this company's detected contradictions — pairs of claims that
        assert incompatible positions on the same topic, across time or
        documents. `min_severity` is 'low', 'medium', or 'high' and filters to
        that severity and above (default 'low' returns all)."""
        sevs = deps.severities_at_least(min_severity)
        rows = [dict(r) for r in deps.neo4j().run(
            queries.CONTRADICTIONS, ticker=ticker, severities=sevs)]
        if not rows:
            return "No contradictions found at that severity.", []
        # Each claim id gets its own [id] bracket so the model can cite either
        # side directly, and the artifact carries both claim_ids (one row per
        # claim) so the output guardrail's grounding check recognizes them —
        # without this the model has to make extra get_citation calls to cite a
        # contradiction, which a leaner orchestrator skips.
        lines = [
            f"{r['topic_name']} — severity {r['severity']}: {r['reasoning']}\n"
            f"  A [{r['a_id']}] ({r['a_date']}, {r['a_speaker']}, {_source_tag(r['a_source'])}): "
            f"\"{r['a_quote']}\"\n"
            f"  B [{r['b_id']}] ({r['b_date']}, {r['b_speaker']}, {_source_tag(r['b_source'])}): "
            f"\"{r['b_quote']}\""
            for r in rows
        ]
        artifact: list[dict] = []
        for r in rows:
            artifact.append({"claim_id": r["a_id"], "source_type": r["a_source"]})
            artifact.append({"claim_id": r["b_id"], "source_type": r["b_source"]})
        return "\n\n".join(lines), artifact

    @tool(response_format="content_and_artifact")
    def list_speakers() -> tuple[str, list[dict]]:
        """List every named speaker (executives, or 'Company' for unattributed
        filing text) who has made claims for this company, with how many."""
        rows = [dict(r) for r in deps.neo4j().run(_SPEAKERS_FOR_TICKER, ticker=ticker)]
        if not rows:
            return "No speakers found.", []
        lines = [f"- {r['speaker']} ({r['role'] or 'n/a'}): {r['claims']} claims"
                 for r in rows]
        return "\n".join(lines), rows

    @tool(response_format="content_and_artifact")
    def semantic_search(query: str, limit: int = 8) -> tuple[str, list[dict]]:
        """Search this company's claims by meaning, not just keywords. Use this
        when the question doesn't map cleanly to one topic id, e.g. 'what did
        they say about China' or 'anything about layoffs'."""
        from vector import embedder, qdrant_store
        vec = embedder.embed_one(query)
        coll = deps.cfg().qdrant["claim_collection"]
        hits = qdrant_store.search(deps.qdrant(), coll, vec, limit=limit, ticker=ticker)
        if not hits:
            return "No matching claims found.", []
        lines = [
            f"[{h['claim_id']}] {h['date']} — {h['speaker']} "
            f"[{_source_tag(h['source_type'])}] (topic: {h['topic']}): "
            f"\"{h['quote_span']}\""
            for h in hits
        ]
        return "\n".join(lines), hits

    @tool(response_format="content_and_artifact")
    def get_citation(claim_id: str) -> tuple[str, list[dict]]:
        """Get the exact source citation for one claim_id — the document,
        speaker, and verbatim quote. Use this to double-check a specific claim
        before citing it, or when the user asks where a claim came from."""
        check = deps.neo4j().run(_CLAIM_BELONGS_TO_TICKER, claim_id=claim_id, ticker=ticker)
        if not check or not check[0]["ok"]:
            return "That claim_id does not belong to this company.", []
        cit = citations.build_citation(claim_id)
        if cit is None:
            return "Claim not found.", []
        row = {"claim_id": claim_id, "source_type": cit["claim"]["source_type"]}
        text = (
            f"[{claim_id}] {cit['document']['doc_type']} ({cit['document']['date']}), "
            f"speaker: {cit['claim']['speaker']} "
            f"[{_source_tag(cit['claim']['source_type'])}]: "
            f"\"{cit['claim']['quote_span']}\""
        )
        return text, [row]

    return [list_topics, get_claim_timeline, get_contradictions, list_speakers,
            semantic_search, get_citation]
