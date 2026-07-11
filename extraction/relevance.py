"""Lightweight relevance prefilter for filing chunks (cost control).

Filings run to ~1000+ paragraphs; most are boilerplate irrelevant to the curated
topics. This cheap keyword gate (topic names + aliases) narrows extraction to
chunks likely to contain a topical claim before spending LLM calls. Synthetic
transcripts skip the filter — every turn is claim-worthy and short.
"""

from __future__ import annotations

import re


def build_keyword_matcher(topics: list[dict]):
    terms: set[str] = set()
    for t in topics:
        terms.add(t["name"].lower())
        for a in t.get("aliases", []):
            terms.add(a.lower())
    # Split multiword names into salient tokens too (e.g. "gross margin").
    patterns = [re.compile(r"\b" + re.escape(term) + r"\b", re.I) for term in terms if term]

    def is_relevant(text: str) -> bool:
        return any(p.search(text) for p in patterns)

    return is_relevant


def select_chunks(doc, topics, *, min_len: int = 80, include_tables: bool = False,
                  max_chunks: int | None = None) -> list:
    """Pick chunks worth sending to extraction for a document."""
    if doc.source_type == "synthetic":
        chunks = [c for c in doc.chunks if c.chunk_type == "paragraph"]
        return chunks[:max_chunks] if max_chunks else chunks

    is_relevant = build_keyword_matcher(topics)
    allowed = {"paragraph"} | ({"table"} if include_tables else set())
    out = []
    for c in doc.chunks:
        if c.chunk_type not in allowed or c.is_heading or c.char_len < min_len:
            continue
        if is_relevant(c.text):
            out.append(c)
            if max_chunks and len(out) >= max_chunks:
                break
    return out
