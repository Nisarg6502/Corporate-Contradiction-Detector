"""Checkpoint 1 sanity checks for the parser (network-free).

Uses a small inline HTML fixture that mimics EDGAR's flat ``div > span``
structure, so these run deterministically without hitting SEC.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingestion.parser import parse_filing_html  # noqa: E402

FIXTURE = """
<html><body>
  <div><span>NVIDIA CORPORATION</span></div>
  <div><span>Cover page boilerplate before any Item heading.</span></div>
  <div><span style="font-weight:700">Item 1. Business</span></div>
  <div><span>We design GPUs. Revenue grew this year.</span></div>
  <div><span>Our data center segment expanded significantly.</span></div>
  <div><span style="font-weight:700">Item 1A. Risk Factors</span></div>
  <div><span>Supply chain concentration is a material risk.</span></div>
  <table><tr><td>Metric</td><td>Value</td></tr><tr><td>Revenue</td><td>100</td></tr></table>
</body></html>
"""


def _parse():
    return parse_filing_html(
        FIXTURE, document_id="ACC-1", doc_type="10-K", date="2026-01-01",
        period_of_report=None, source_url="http://x", source_type="real",
        raw_ref="x.html", company={"ticker": "NVDA"},
    )


def test_sections_detected_from_item_headings():
    doc = _parse()
    headings = [s.heading for s in doc.sections]
    assert "Item 1. Business" in headings
    assert "Item 1A. Risk Factors" in headings
    # front-matter (cover page) becomes its own leading section
    assert doc.sections[0].heading == ""


def test_anchors_are_stable_and_wellformed():
    d1, d2 = _parse(), _parse()
    a1 = [(c.chunk_id, c.text) for c in d1.chunks]
    a2 = [(c.chunk_id, c.text) for c in d2.chunks]
    assert a1 == a2, "re-parsing identical HTML must yield identical anchors"
    for c in d1.chunks:
        assert c.chunk_id == f"{c.document_id}#{c.section_id}#p{c.paragraph_index}"


def test_chunk_content_is_clean():
    doc = _parse()
    texts = {c.text for c in doc.chunks}
    assert "We design GPUs. Revenue grew this year." in texts
    # table flattened to readable text
    assert any(c.chunk_type == "table" and "Revenue | 100" in c.text
               for c in doc.chunks)
    # no empty chunks, no replacement chars
    for c in doc.chunks:
        assert c.text.strip()
        assert "�" not in c.text


def test_heading_chunk_starts_section_at_p0():
    doc = _parse()
    for s in doc.sections:
        if s.heading:
            assert s.chunks[0].is_heading
            assert s.chunks[0].paragraph_index == 0
