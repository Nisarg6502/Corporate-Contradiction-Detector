"""Checkpoint 5 sanity checks: candidate prioritization + judgment normalization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from detection.candidates import prioritize  # noqa: E402
from detection.judge import normalize_judgment, build_user  # noqa: E402


def _row(topic, a_source, b_source, a_id="a", b_id="b"):
    return {"topic": topic, "a_id": a_id, "b_id": b_id,
            "a_source": a_source, "b_source": b_source,
            "a_date": "2025-01-01", "b_date": "2026-01-01",
            "a_speaker": "X", "b_speaker": "Y", "a_doctype": "earnings_call",
            "b_doctype": "10-K", "a_quote": "qa", "b_quote": "qb"}


def test_cross_source_only_filters_same_source():
    rows = [_row("t1", "synthetic", "real"), _row("t2", "real", "real")]
    out = prioritize(rows, cross_source_only=True)
    assert len(out) == 1 and out[0]["topic"] == "t1"


def test_all_pairs_keeps_same_source_but_cross_first():
    rows = [_row("t2", "real", "real"), _row("t1", "synthetic", "real")]
    out = prioritize(rows, cross_source_only=False)
    assert len(out) == 2
    assert out[0]["a_source"] != out[0]["b_source"]  # cross-source ranked first


def test_max_pairs_caps():
    rows = [_row(f"t{i}", "synthetic", "real") for i in range(10)]
    assert len(prioritize(rows, max_pairs=3)) == 3


def test_normalize_true_contradiction_keeps_severity():
    v = normalize_judgment({"contradicts": True, "severity": "high", "reasoning": "opposite"})
    assert v == {"contradicts": True, "severity": "high", "reasoning": "opposite"}


def test_normalize_false_forces_none_severity():
    v = normalize_judgment({"contradicts": False, "severity": "high", "reasoning": "n/a"})
    assert v["contradicts"] is False and v["severity"] == "none"


def test_normalize_handles_key_aliases_and_bad_severity():
    v = normalize_judgment({"is_contradiction": True, "severity": "critical",
                            "explanation": "x"})
    assert v["contradicts"] is True
    assert v["severity"] == "medium"   # unknown severity on a true contradiction -> medium
    assert v["reasoning"] == "x"


def test_build_user_includes_both_quotes_and_topic():
    u = build_user(_row("gross_margin", "synthetic", "real"))
    assert "gross_margin" in u and "qa" in u and "qb" in u
