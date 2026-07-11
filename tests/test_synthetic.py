"""Checkpoint 2 sanity checks for the synthetic transcript PDF path.

Generates a PDF from an inline transcript, parses it via PyMuPDF, and asserts
speaker attribution, source_type tagging, position data, and — most important —
that a quote span resolves to a highlight rect on the recorded page (the
property the citation viewer depends on).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

fitz = pytest.importorskip("fitz")  # PyMuPDF

from ingestion import pdf_generator, pdf_parser  # noqa: E402

TRANSCRIPT = {
    "document_id": "SYN-TEST",
    "doc_type": "earnings_call",
    "date": "2025-01-01",
    "quarter": "Q1 FY2026",
    "company": {"ticker": "NVDA", "name": "NVIDIA Corporation"},
    "title": "NVIDIA Corporation - Test Earnings Call",
    "turns": [
        {"speaker": "Colette Kress", "role": "Chief Financial Officer",
         "text": "Our gross margin expanded to a record level this quarter "
                 "with no meaningful inventory charges of any kind."},
        {"speaker": "Jensen Huang", "role": "Chief Executive Officer",
         "text": "Demand for our platform continues to outpace supply and "
                 "data center revenue reached a new record."},
    ],
}


@pytest.fixture()
def parsed(tmp_path):
    pdf_path = pdf_generator.generate_pdf(TRANSCRIPT, out_dir=tmp_path)
    doc = pdf_parser.parse_pdf(
        pdf_path, document_id=TRANSCRIPT["document_id"],
        doc_type=TRANSCRIPT["doc_type"], date=TRANSCRIPT["date"],
        company=TRANSCRIPT["company"],
    )
    return pdf_path, doc


def test_source_type_and_speakers(parsed):
    _, doc = parsed
    assert doc.source_type == "synthetic"
    speakers = [c.speaker for c in doc.chunks]
    assert speakers == ["Colette Kress", "Jensen Huang"]
    assert all(c.page == 1 and c.bbox for c in doc.chunks)


def test_text_fidelity(parsed):
    _, doc = parsed
    kress = doc.chunks[0].text
    assert "gross margin expanded to a record level" in kress
    assert "no meaningful inventory charges" in kress
    assert all(ord(ch) <= 126 for ch in kress)  # no glyph mojibake


def test_quote_span_is_highlightable(parsed):
    pdf_path, doc = parsed
    quote = "gross margin expanded to a record level"
    rects = pdf_parser.find_highlight_rects(pdf_path, doc.chunks[0].page, quote)
    assert rects, "quote span must resolve to at least one highlight rect"
    for r in rects:
        assert r[2] > r[0] and r[3] > r[1]  # non-degenerate rect


def test_page_image_extraction(parsed):
    pdf_path, doc = parsed
    png = pdf_parser.render_page_png(pdf_path, 1, dpi=100)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic
