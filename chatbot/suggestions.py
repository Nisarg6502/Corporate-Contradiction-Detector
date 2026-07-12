"""Suggested starter questions for a company's chat panel empty state.

Seeded from the company's actual topics/contradictions (never invented), with
a light LLM pass to phrase them naturally. Falls back to a template-based list
if the LLM call fails — this is a discoverability nicety, not core chat, so it
should never block the chat panel from rendering.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from api import deps
from config import get_config
from graph import queries
from observability import obs

from .llm import build_chat_llm

_SYSTEM = """You write short, natural starter questions for a chat assistant about \
one company's SEC filings and detected contradictions. Given the topics and \
contradictions already found for this company, write exactly {n} distinct, \
specific questions a curious user might ask. Each under 12 words. One per \
line, no numbering, no other text."""

_FOLLOWUP_SYSTEM = """You suggest follow-up questions for a chat assistant about \
{company}'s SEC filings and detected contradictions. Given the user's last \
question and the assistant's answer, write exactly {n} short, natural \
follow-up questions that dig deeper into the SAME subject or an obviously \
related one the answer hints at. Each under 12 words, specific to this \
company's filings, answerable from filings/contradictions (never investment \
advice). One per line, no numbering, no quotes, no other text."""


def _fallback_questions(topics: list[dict], contradictions: list[dict], n: int) -> list[str]:
    qs = [f"What contradiction did you find about {c['topic_name'].lower()}?"
          for c in contradictions[:2]]
    for t in topics:
        if len(qs) >= n:
            break
        qs.append(f"What has the company said about {t['name'].lower()}?")
    return qs[:n]


def suggested_questions(ticker: str, n: int = 5) -> list[str]:
    cfg = get_config()
    topics = [dict(r) for r in deps.neo4j().run(queries.TOPICS_WITH_COUNTS, ticker=ticker)]
    if not topics:
        return []
    contradictions = [dict(r) for r in deps.neo4j().run(
        queries.CONTRADICTIONS, ticker=ticker, severities=["medium", "high"])]
    fallback = _fallback_questions(topics, contradictions, n)

    try:
        llm = build_chat_llm(cfg, "synthesis")
        model = cfg.models["chat"]["synthesis"]["model"]
        lines = ["Topics: " + ", ".join(t["name"] for t in topics[:9])]
        if contradictions:
            lines.append("Contradictions: " + "; ".join(
                f"{c['topic_name']} ({c['severity']})" for c in contradictions[:5]))
        prompt = "\n".join(lines)
        system = _SYSTEM.format(n=n)
        with obs.generation("chat-suggestions", model,
                             prompt={"system": system, "user": prompt},
                             metadata={"ticker": ticker, "stage": "suggestions"}) as gen:
            resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
            gen.finish(output=resp.content)
        questions = [l.strip(" -\t") for l in (resp.content or "").splitlines() if l.strip()]
        return questions[:n] if questions else fallback
    except Exception:
        return fallback


def followup_questions(ticker: str, company_name: str, question: str,
                       answer: str, n: int = 3) -> list[str]:
    """Contextual follow-up questions generated from the just-finished turn.

    Runs on the fast guardrail model (small, reasoning-off) and is called
    *after* the answer has streamed, so it never delays the answer itself.
    Returns [] on any failure — follow-up chips are a nicety, not core chat.
    """
    if not (question or "").strip() or not (answer or "").strip():
        return []
    cfg = get_config()
    try:
        llm = build_chat_llm(cfg, "guardrail")
        model = cfg.models["chat"]["guardrail"]["model"]
        system = _FOLLOWUP_SYSTEM.format(company=company_name or ticker, n=n)
        # Trim both fields so an oversized body can't blow the small model's
        # context or slow it down — the gist is enough to propose follow-ups.
        user = f"USER ASKED: {question.strip()[:500]}\n\nASSISTANT ANSWERED: {answer.strip()[:1500]}"
        with obs.generation("chat-followups", model,
                             prompt={"system": system, "user": user},
                             metadata={"ticker": ticker, "stage": "followups"}) as gen:
            resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
            gen.finish(output=resp.content)
        lines = [l.strip(" -*\t\"'") for l in (resp.content or "").splitlines() if l.strip()]
        # Drop anything that leaked numbering or is implausibly long.
        clean = [l for l in lines if 3 <= len(l) <= 120]
        return clean[:n]
    except Exception:
        return []
