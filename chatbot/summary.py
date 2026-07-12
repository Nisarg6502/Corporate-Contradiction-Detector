"""Auto-generated executive summary: what the filings and detected
contradictions show for one company, narrated with inline citations. Uses the
same synthesis model + grounding-citation convention as chat answers, but as
a single call over the company's top topics/contradictions rather than a
tool-calling loop — there's no user question to route, just "summarize what
you found."
"""

from __future__ import annotations

from typing import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage

from api import deps
from config import get_config
from graph import queries
from observability import obs

from .guardrails import extract_citations
from .llm import build_chat_llm

SUMMARY_SYSTEM = """You write a short executive summary of what a company's SEC \
filings and detected contradictions show, for a research tool called \
Counterpoint. The company is named in the context below (COMPANY: ...) — use \
that name, never a placeholder like "Company X". Use ONLY the topics and \
contradictions listed below — never outside knowledge about the company. \
Cite every specific claim inline with \
its bracketed id exactly as given, e.g. "...improving [abc123...]." Put \
NOTHING else inside the brackets (no "synthetic"/"real" tag, no extra words) \
— state the real-vs-synthetic distinction in the sentence itself, not inside \
the citation brackets. Preserve the real filing vs SYNTHETIC DEMO DATA \
distinction on every claim you use. Write 3-5 short paragraphs: what the \
company claims across its key topics, then any contradictions found and why \
they matter. Never give investment \
advice."""


_MAX_CLAIMS_PER_TOPIC = 4


def _gather_context(ticker: str, company_name: str) -> str | None:
    topics = [dict(r) for r in deps.neo4j().run(queries.TOPICS_WITH_COUNTS, ticker=ticker)]
    if not topics:
        return None
    contradictions = [dict(r) for r in deps.neo4j().run(
        queries.CONTRADICTIONS, ticker=ticker, severities=["low", "medium", "high"])]

    # Sample a few citable claims per topic, not just counts — without this,
    # a company with zero detected contradictions gives the model nothing to
    # cite (it can only see "8 claims" for a topic, never the claim text or
    # id), and it correctly refuses to write a summary with citations.
    lines = [f"COMPANY: {company_name} ({ticker})", "", "TOPICS AND SAMPLE CLAIMS:"]
    for t in topics:
        lines.append(f"\n- {t['topic']} ({t['name']}): {t['claims']} claims"
                      + (f", {t['synthetic']} synthetic" if t["synthetic"] else ""))
        claims = [dict(r) for r in deps.neo4j().run(
            queries.CLAIMS_FOR_TOPIC, ticker=ticker, topic=t["topic"])]
        for c in claims[:_MAX_CLAIMS_PER_TOPIC]:
            tag = "SYNTHETIC DEMO DATA" if c["source"] == "synthetic" else "real filing"
            lines.append(
                f"  [{c['claim_id']}] {c['date']} — {c['speaker'] or 'n/a'}, "
                f"{c['doc_type']} [{tag}]: \"{c['quote']}\"")
    if contradictions:
        lines.append("\nCONTRADICTIONS:")
        for c in contradictions[:15]:
            tag_a = "SYNTHETIC DEMO DATA" if c["a_source"] == "synthetic" else "real filing"
            tag_b = "SYNTHETIC DEMO DATA" if c["b_source"] == "synthetic" else "real filing"
            lines.append(
                f"[{c['a_id']} vs {c['b_id']}] {c['topic_name']} — severity "
                f"{c['severity']}: {c['reasoning']}\n"
                f"  A ({c['a_date']}, {c['a_speaker']}, {tag_a}): \"{c['a_quote']}\"\n"
                f"  B ({c['b_date']}, {c['b_speaker']}, {tag_b}): \"{c['b_quote']}\"")
    return "\n".join(lines)


def executive_summary(ticker: str, company_name: str | None = None) -> dict:
    """Non-streaming variant: {"summary": str, "cited_ids": list[str]}."""
    cfg = get_config()
    context = _gather_context(ticker, company_name or ticker)
    if context is None:
        return {"summary": "No processed data found for this company yet.", "cited_ids": []}
    llm = build_chat_llm(cfg, "synthesis")
    model = cfg.models["chat"]["synthesis"]["model"]
    with obs.generation("chat-summary", model,
                         prompt={"system": SUMMARY_SYSTEM, "user": context},
                         metadata={"ticker": ticker, "stage": "summary"}) as gen:
        resp = llm.invoke([SystemMessage(content=SUMMARY_SYSTEM), HumanMessage(content=context)])
        gen.finish(output=resp.content)
    return {"summary": resp.content, "cited_ids": sorted(extract_citations(resp.content or ""))}


async def astream_executive_summary(ticker: str, company_name: str | None = None) -> AsyncIterator[str]:
    """Streaming variant, for the SSE endpoint — yields text deltas."""
    cfg = get_config()
    context = _gather_context(ticker, company_name or ticker)
    if context is None:
        yield "No processed data found for this company yet."
        return
    llm = build_chat_llm(cfg, "synthesis")
    async for chunk in llm.astream([SystemMessage(content=SUMMARY_SYSTEM),
                                     HumanMessage(content=context)]):
        if chunk.content:
            yield chunk.content
