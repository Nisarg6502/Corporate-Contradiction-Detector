"""BeautifulSoup HTML -> structured, anchored chunks.

Turns a raw EDGAR filing (iXBRL HTML) into a :class:`Document` of sections and
paragraph-level chunks. The parse is deterministic: identical input HTML always
yields identical text and identical position anchors, which is what makes the
citation feature trustworthy.

Approach (validated against NVDA's Workiva-generated 10-K):
  * Drop hidden iXBRL metadata (``ix:header``) and non-visual tags.
  * Walk the tree yielding *leaf blocks* (block elements with no block-element
    descendants) in document order; tables are yielded whole and flattened.
  * Numbers wrapped in ``ix:nonfraction`` / ``ix:nonnumeric`` are preserved
    because we read visible text via ``get_text``.
  * Section boundaries are the canonical 10-K/10-Q "Item N." / "Part N" markers
    plus real heading tags (h1-h6). Sub-headings are kept as their own chunks so
    no structure is lost.
"""

from __future__ import annotations

import re
import warnings
from datetime import datetime, timezone

from bs4 import BeautifulSoup, NavigableString, Tag
from bs4 import XMLParsedAsHTMLWarning

from .models import Chunk, Document, Section

# EDGAR iXBRL files carry an <?xml?> prolog; we deliberately parse them with the
# lenient HTML parser (it yields cleaner block structure here), so silence the
# advisory warning.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Block-level tags. Tables are handled separately (flattened whole).
_BLOCK_TAGS = {"div", "p", "li", "blockquote", "section", "article",
               "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_SKIP_TAGS = {"script", "style", "head", "title", "meta", "link"}

# Canonical filing section markers, e.g. "Item 1A." / "Item 7." / "PART II".
_SECTION_RE = re.compile(r"^\s*(item\s+\d+[a-z]?\.|part\s+[ivx]+\b)", re.IGNORECASE)

_WS_RE = re.compile(r"\s+")


def _norm(text: str) -> str:
    """Collapse whitespace; normalize common punctuation mojibake."""
    text = text.replace("\xa0", " ")
    text = (text.replace("’", "'").replace("‘", "'")
                .replace("“", '"').replace("”", '"')
                .replace("–", "-").replace("—", "-"))
    return _WS_RE.sub(" ", text).strip()


def _is_block(el: Tag) -> bool:
    return isinstance(el, Tag) and el.name in _BLOCK_TAGS


def _has_block_descendant(el: Tag) -> bool:
    return any(isinstance(d, Tag) and (d.name in _BLOCK_TAGS or d.name == "table")
               for d in el.descendants)


def _flatten_table(table: Tag) -> str:
    """Render a table as readable text: cells joined by ' | ', rows by newline."""
    lines = []
    for row in table.find_all("tr"):
        cells = [_norm(c.get_text(" ", strip=True))
                 for c in row.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if cells:
            lines.append(" | ".join(cells))
    return "\n".join(lines)


def _iter_blocks(root: Tag):
    """Yield ('table'|'block', Tag) in document order.

    A table is yielded whole (not descended into). Other block elements are
    yielded only when they are *leaf blocks* (no block/table descendants);
    containers are descended into so we never emit a parent and its children.
    """
    for child in root.children:
        if isinstance(child, NavigableString):
            continue
        if not isinstance(child, Tag):
            continue
        if child.name in _SKIP_TAGS:
            continue
        style = (child.get("style") or "").replace(" ", "").lower()
        if "display:none" in style:
            continue
        if child.name == "table":
            yield "table", child
        elif _is_block(child) and not _has_block_descendant(child):
            yield "block", child
        else:
            # Container (or inline wrapper): descend to find leaf blocks.
            yield from _iter_blocks(child)


def _classify_heading(text: str, tag_name: str) -> bool:
    if tag_name in _HEADING_TAGS:
        return True
    return bool(_SECTION_RE.match(text))


def parse_filing_html(html: str, *, document_id: str, doc_type: str, date: str,
                      period_of_report: str | None, source_url: str,
                      source_type: str, raw_ref: str, company: dict) -> Document:
    soup = BeautifulSoup(html, "lxml")

    # Remove hidden iXBRL metadata block and non-visual tags.
    header = soup.find("ix:header")
    if header:
        header.decompose()
    for t in soup(list(_SKIP_TAGS)):
        t.decompose()

    body = soup.body or soup
    doc = Document(
        document_id=document_id, doc_type=doc_type, date=date,
        period_of_report=period_of_report, source_url=source_url,
        source_type=source_type, raw_ref=raw_ref, company=company,
        parsed_at=datetime.now(timezone.utc).isoformat(),
    )

    def new_section(heading: str) -> Section:
        ordinal = len(doc.sections)
        section = Section(section_id=f"s{ordinal:03d}", ordinal=ordinal,
                          heading=heading)
        doc.sections.append(section)
        return section

    current: Section | None = None  # created lazily -> no empty sections

    for kind, el in _iter_blocks(body):
        if kind == "table":
            text = _flatten_table(el)
            if not text:
                continue
            chunk_type, is_heading = "table", False
        else:
            text = _norm(el.get_text(" ", strip=True))
            if not text:
                continue
            is_heading = _classify_heading(text, el.name)
            chunk_type = "heading" if is_heading else "paragraph"

        # A canonical section heading starts a new section.
        section_break = is_heading and (el.name in _HEADING_TAGS
                                        or _SECTION_RE.match(text))
        if section_break:
            current = new_section(text)
        elif current is None:
            current = new_section("")  # front-matter, before any heading

        idx = len(current.chunks)
        current.chunks.append(Chunk(
            chunk_id=f"{document_id}#{current.section_id}#p{idx}",
            document_id=document_id, section_id=current.section_id,
            paragraph_index=idx, text=text, chunk_type=chunk_type,
            is_heading=is_heading, char_len=len(text),
        ))

    return doc
