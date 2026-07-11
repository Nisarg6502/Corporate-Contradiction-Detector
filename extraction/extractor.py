"""Per-chunk claim extraction with the quote-span guardrail + retry loop.

`extract_claims_for_chunk` is LLM-agnostic: it takes a `llm_call` closure, so it
runs identically against the real Haiku client or a fake in tests. On a
quote-span failure it retries with a corrective instruction, accumulating the
claims that DO validate across attempts (deduped by verbatim span + topic).
"""

from __future__ import annotations

from datetime import datetime, timezone

from .guardrail import validate_claims
from .prompt import build_system, build_user
from .schema import Claim, make_claim_id

# Models vary in exact key names; normalize to our canonical schema and drop
# anything without a valid curated topic + a quote span.
_TOPIC_KEYS = ("topic", "topic_id", "topicId", "topic_name")
_QUOTE_KEYS = ("quote_span", "quote", "span", "source_quote")
_CLAIM_KEYS = ("claim_text", "claim", "text")


def _first(raw: dict, keys) -> str:
    for k in keys:
        v = raw.get(k)
        if v:
            return v
    return ""


def _normalize_raw(raw: dict, topic_ids: list[str]) -> dict | None:
    topic = _first(raw, _TOPIC_KEYS)
    quote = _first(raw, _QUOTE_KEYS)
    if topic not in topic_ids or not quote:
        return None
    val = raw.get("value_numeric")
    return {
        "topic": topic,
        "quote_span": quote,
        "claim_text": _first(raw, _CLAIM_KEYS),
        "stance": raw.get("stance", ""),
        "speaker": raw.get("speaker", ""),
        "role": raw.get("role", ""),
        "value_numeric": val if isinstance(val, (int, float)) else None,
    }


def extract_claims_for_chunk(chunk, doc, *, llm_call, topics,
                             max_retries: int = 2, model_name: str = "") -> list[Claim]:
    topic_ids = [t["id"] for t in topics]
    system = build_system(topics)
    doc_label = f"{doc.company.get('ticker','')} {doc.doc_type} {doc.date}"
    user = build_user(chunk.text, speaker_hint=chunk.speaker, doc_label=doc_label)

    accepted: dict[tuple, dict] = {}   # (topic, span) -> raw claim
    for attempt in range(max_retries + 1):
        raw = llm_call(system, user, topic_ids)
        raw = [n for n in (_normalize_raw(r, topic_ids) for r in raw) if n]
        valid, invalid = validate_claims(chunk.text, raw)
        for c in valid:
            accepted[(c["topic"], c["quote_span"])] = c
        if not invalid:
            break
        if attempt < max_retries:
            bad = "; ".join(repr(c.get("quote_span", "")[:80]) for c in invalid)
            user = (build_user(chunk.text, speaker_hint=chunk.speaker, doc_label=doc_label)
                    + f"\n\nThese quote_spans were NOT exact substrings and were "
                      f"rejected: {bad}. Re-copy every quote_span VERBATIM from the "
                      f"SOURCE TEXT, character for character.")

    now = datetime.now(timezone.utc).isoformat()
    claims: list[Claim] = []
    for c in accepted.values():
        span = c["quote_span"]
        topic = c["topic"]
        speaker = chunk.speaker or c.get("speaker") or "Company"
        role = chunk.speaker_role or c.get("role") or ""
        claims.append(Claim(
            claim_id=make_claim_id(chunk.chunk_id, topic, span),
            document_id=chunk.document_id, chunk_id=chunk.chunk_id,
            section_id=chunk.section_id, paragraph_index=chunk.paragraph_index,
            topic=topic, speaker=speaker, role=role,
            claim_text=c.get("claim_text", ""), quote_span=span,
            stance=c.get("stance", ""), value_numeric=c.get("value_numeric"),
            date=doc.date, source_type=doc.source_type, doc_type=doc.doc_type,
            company_ticker=doc.company.get("ticker", ""),
            page=chunk.page, bbox=chunk.bbox,
            extracted_by=model_name, extracted_at=now,
        ))
    return claims
