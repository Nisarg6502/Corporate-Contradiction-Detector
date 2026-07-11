"""Data model for the ingestion intermediate store.

A parsed filing is a :class:`Document` holding an ordered list of
:class:`Section` s, each holding an ordered list of :class:`Chunk` s. Every
chunk carries a stable *position anchor* (``document_id``, ``section_id``,
``paragraph_index``) so a later citation can point back to the exact source
location, and re-parsing the same raw file yields identical anchors.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Chunk:
    chunk_id: str            # "{document_id}#{section_id}#p{paragraph_index}"
    document_id: str
    section_id: str
    paragraph_index: int
    text: str
    chunk_type: str          # "paragraph" | "heading" | "table"
    is_heading: bool
    char_len: int
    # Transcript-only: which speaker uttered this chunk (None for filings).
    speaker: Optional[str] = None
    speaker_role: Optional[str] = None
    # PDF-only position data for highlight rendering (None for HTML filings):
    # 1-based page number and [x0, y0, x1, y1] bbox in PDF points.
    page: Optional[int] = None
    bbox: Optional[list] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Section:
    section_id: str          # "s{ordinal:03d}"
    ordinal: int
    heading: str             # heading text ("" for front-matter before 1st heading)
    chunks: list[Chunk] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["chunks"] = [c.to_dict() for c in self.chunks]
        return d


@dataclass
class Document:
    document_id: str         # SEC accession number (with dashes)
    doc_type: str            # "10-K" | "10-Q" | "8-K"
    date: str                # filing date (ISO)
    period_of_report: Optional[str]
    source_url: str
    source_type: str         # "real" | "synthetic"
    raw_ref: str             # path to the cached raw HTML on disk
    company: dict            # {ticker, cik, name}
    parsed_at: str
    sections: list[Section] = field(default_factory=list)

    @property
    def chunks(self) -> list[Chunk]:
        return [c for s in self.sections for c in s.chunks]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["sections"] = [s.to_dict() for s in self.sections]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        sections = []
        for sd in d.get("sections", []):
            chunks = [Chunk(**cd) for cd in sd.get("chunks", [])]
            sd = {k: v for k, v in sd.items() if k != "chunks"}
            sections.append(Section(chunks=chunks, **sd))
        d = {k: v for k, v in d.items() if k != "sections"}
        return cls(sections=sections, **d)
