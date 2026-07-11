"""Build citation payloads that trace a claim back to its exact source.

Real filings -> structured HTML render data (section heading + paragraph text +
the exact quote to highlight inline). Synthetic PDFs -> page + bbox + precise
highlight rects (via PyMuPDF search_for) for an image overlay.
"""

from __future__ import annotations

from extraction import claim_store
from ingestion import pdf_parser, store


def build_citation(claim_id: str) -> dict | None:
    claims = claim_store.load_claims()
    c = claims.get(claim_id)
    if c is None:
        return None
    doc = store.load_document(c.document_id)
    chunk = next((ch for ch in doc.chunks if ch.chunk_id == c.chunk_id), None)
    section = next((s for s in doc.sections if s.section_id == c.section_id), None)

    citation = {
        "claim": {
            "claim_id": c.claim_id, "topic": c.topic, "speaker": c.speaker,
            "role": c.role, "stance": c.stance, "quote_span": c.quote_span,
            "date": c.date, "source_type": c.source_type,
        },
        "document": {
            "document_id": doc.document_id, "doc_type": doc.doc_type,
            "date": doc.date, "period": doc.period_of_report,
            "source_type": doc.source_type, "source_url": doc.source_url,
        },
        "anchor": {"section_id": c.section_id, "paragraph_index": c.paragraph_index,
                   "page": c.page},
    }

    # Both source types carry the paragraph text + the exact span so the viewer
    # can render "book page" text with the quote highlighted inline (per design).
    render = {
        "type": "html" if doc.source_type == "real" else "pdf",
        "section_heading": section.heading if section else "",
        "paragraph_text": chunk.text if chunk else "",
        "quote_span": c.quote_span,
    }
    if doc.source_type == "synthetic":
        render["page"] = c.page
        render["bbox"] = c.bbox
        render["highlight_rects"] = (
            pdf_parser.find_highlight_rects(doc.raw_ref, c.page, c.quote_span)
            if c.page else []
        )
    citation["render"] = render
    return citation
