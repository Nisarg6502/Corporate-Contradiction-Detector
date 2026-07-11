"""Checkpoint 3 sanity checks: the quote-span guardrail + extractor retry loop.

Network-free — a fake llm_call stands in for Claude. The guardrail is the
project's load-bearing invariant, so it gets the most coverage.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from extraction.guardrail import recover_verbatim_span, validate_claims  # noqa: E402
from extraction.extractor import extract_claims_for_chunk  # noqa: E402
from ingestion.models import Chunk, Document, Section  # noqa: E402

TOPICS = [{"id": "gross_margin_profitability", "name": "Gross margin",
           "description": "margins", "aliases": ["gross margin"]}]


def _doc_and_chunk(text):
    doc = Document(document_id="D1", doc_type="10-K", date="2026-01-01",
                   period_of_report=None, source_url="", source_type="real",
                   raw_ref="", company={"ticker": "NVDA"}, parsed_at="")
    chunk = Chunk(chunk_id="D1#s000#p0", document_id="D1", section_id="s000",
                  paragraph_index=0, text=text, chunk_type="paragraph",
                  is_heading=False, char_len=len(text))
    doc.sections.append(Section(section_id="s000", ordinal=0, heading="", chunks=[chunk]))
    return doc, chunk


def test_recover_exact_and_whitespace():
    src = "Gross margin decreased in fiscal year 2026 due to a charge."
    assert recover_verbatim_span(src, "Gross margin decreased") == "Gross margin decreased"
    # Model re-flowed whitespace -> recovered slice is the real source text.
    assert recover_verbatim_span(src, "Gross   margin\n decreased") == "Gross margin decreased"
    assert recover_verbatim_span(src, "margins went up") is None


def test_validate_splits_valid_invalid():
    src = "Revenue grew 50% year over year."
    valid, invalid = validate_claims(src, [
        {"topic": "t", "quote_span": "Revenue grew 50%"},
        {"topic": "t", "quote_span": "Revenue fell"},
    ])
    assert len(valid) == 1 and valid[0]["quote_span"] == "Revenue grew 50%"
    assert len(invalid) == 1


def test_extractor_drops_hallucinated_spans_after_retries():
    text = "Gross margin decreased in fiscal year 2026."
    doc, chunk = _doc_and_chunk(text)
    calls = {"n": 0}

    def fake_llm(system, user, topic_ids):
        calls["n"] += 1
        return [
            {"topic": "gross_margin_profitability", "speaker": "Company", "role": "",
             "claim_text": "margin down", "quote_span": "Gross margin decreased",
             "stance": "margin decreasing", "value_numeric": None},
            {"topic": "gross_margin_profitability", "speaker": "Company", "role": "",
             "claim_text": "made up", "quote_span": "margin skyrocketed",  # not in source
             "stance": "x", "value_numeric": None},
        ]

    claims = extract_claims_for_chunk(chunk, doc, llm_call=fake_llm, topics=TOPICS,
                                      max_retries=2, model_name="fake")
    # Only the verbatim claim survives; the hallucinated one is dropped.
    assert len(claims) == 1
    assert claims[0].quote_span == "Gross margin decreased"
    assert claims[0].quote_span in text
    # It retried because an invalid span was present each time.
    assert calls["n"] == 3


def test_extractor_stops_early_when_all_valid():
    text = "Gross margin decreased in fiscal year 2026."
    doc, chunk = _doc_and_chunk(text)
    calls = {"n": 0}

    def fake_llm(system, user, topic_ids):
        calls["n"] += 1
        return [{"topic": "gross_margin_profitability", "speaker": "Company", "role": "",
                 "claim_text": "margin down", "quote_span": "Gross margin decreased",
                 "stance": "margin decreasing", "value_numeric": None}]

    claims = extract_claims_for_chunk(chunk, doc, llm_call=fake_llm, topics=TOPICS,
                                      max_retries=2, model_name="fake")
    assert len(claims) == 1
    assert calls["n"] == 1  # no retry when everything validates
