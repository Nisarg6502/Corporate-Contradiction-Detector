"""Extraction prompt construction (topic-constrained, quote-span-strict)."""

from __future__ import annotations


def build_system(topics: list[dict]) -> str:
    lines = [
        "You extract factual and strategic CLAIMS made by a company or its named "
        "executives from SEC filings and earnings-call excerpts.",
        "",
        "Rules:",
        "- Only extract claims that fit ONE of the allowed topics below. If the text "
        "has no such claim, return an empty list.",
        "- A claim must be substantive (a factual assertion, projection, denial, or "
        "commitment) — never boilerplate, headings, or generic risk-factor throat-clearing.",
        "- `quote_span` MUST be copied VERBATIM, character-for-character, from the "
        "SOURCE TEXT provided. Do not paraphrase, trim, or fix it. If you cannot quote "
        "it exactly, do not emit the claim.",
        "- Keep `quote_span` focused (one sentence or clause), not a whole paragraph.",
        "- `claim_text` is your own concise paraphrase; `stance` is a short directional "
        "summary usable to compare claims over time.",
        "",
        "Allowed topics (use the id):",
    ]
    for t in topics:
        lines.append(f"- {t['id']}: {t['name']} — {t['description'].strip()}")
    return "\n".join(lines)


def build_user(chunk_text: str, *, speaker_hint: str | None, doc_label: str) -> str:
    parts = [f"DOCUMENT: {doc_label}"]
    if speaker_hint:
        parts.append(f"SPEAKER (authoritative — use this as the speaker): {speaker_hint}")
    parts.append("")
    parts.append("SOURCE TEXT (quote spans must come verbatim from between the fences):")
    parts.append("<<<")
    parts.append(chunk_text)
    parts.append(">>>")
    return "\n".join(parts)
