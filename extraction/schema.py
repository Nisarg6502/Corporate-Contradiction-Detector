"""Claim schema + the strict tool-use input schema for extraction.

The stored `Claim` carries everything downstream checkpoints need: the position
anchor (document_id/section_id/paragraph_index), the topic, the speaker, the
verbatim `quote_span` (the project's hard constraint), and — for synthetic PDFs
— the page/bbox for the citation viewer.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class Claim:
    claim_id: str
    document_id: str
    chunk_id: str
    section_id: str
    paragraph_index: int
    topic: str
    speaker: str
    role: str
    claim_text: str
    quote_span: str          # verified exact substring of the source chunk
    stance: str
    value_numeric: Optional[float]
    date: str
    source_type: str         # real | synthetic
    doc_type: str
    company_ticker: str
    page: Optional[int] = None
    bbox: Optional[list] = None
    extracted_by: str = ""
    extracted_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Claim":
        return cls(**d)


def make_claim_id(chunk_id: str, topic: str, quote_span: str) -> str:
    """Deterministic id → graph upserts are idempotent across re-runs."""
    h = hashlib.sha1(f"{chunk_id}|{topic}|{quote_span}".encode("utf-8")).hexdigest()
    return h[:16]


def build_extraction_tool(topic_ids: list[str]) -> dict:
    """Strict tool schema Claude must fill. Constrains topic to the curated list.

    document_id / position_anchor / date are attached by us afterward (we know
    them for the chunk) so the model can't hallucinate anchors.
    """
    claim_item = {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "enum": topic_ids,
                      "description": "The single best-matching curated topic id."},
            "speaker": {"type": "string",
                        "description": "Who made the claim. For filings with no "
                                       "named individual, use 'Company'."},
            "role": {"type": "string",
                     "description": "Speaker's role/title, or '' if unknown."},
            "claim_text": {"type": "string",
                           "description": "Concise paraphrase of the specific claim."},
            "quote_span": {"type": "string",
                           "description": "EXACT substring copied verbatim from the "
                                          "SOURCE TEXT that supports the claim."},
            "stance": {"type": "string",
                       "description": "Short directional position, e.g. 'gross margin "
                                      "increasing' or 'no customer concentration risk'."},
            "value_numeric": {
                "anyOf": [{"type": "number"}, {"type": "null"}],
                "description": "Key numeric value if the claim states one, else null.",
            },
        },
        "required": ["topic", "speaker", "role", "claim_text", "quote_span",
                     "stance", "value_numeric"],
        "additionalProperties": False,
    }
    return {
        "name": "emit_claims",
        "description": "Emit the factual/strategic claims found in the source text. "
                       "Return an empty list if the text contains no claim on any of "
                       "the allowed topics.",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {"claims": {"type": "array", "items": claim_item}},
            "required": ["claims"],
            "additionalProperties": False,
        },
    }
