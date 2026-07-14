"""Unit tests for the bounded-retry helper (network-free, fast).

Backoff sleeps are patched to no-ops so these run instantly.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from observability import retry  # noqa: E402
from observability.retry import is_transient, with_retry  # noqa: E402


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(retry.time, "sleep", lambda *_: None)


def test_returns_immediately_on_success():
    calls = []

    def ok():
        calls.append(1)
        return "value"

    assert with_retry(ok, attempts=3) == "value"
    assert len(calls) == 1  # no retries on success


def test_retries_transient_then_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("connection reset by peer")
        return "ok"

    assert with_retry(flaky, attempts=3) == "ok"
    assert calls["n"] == 3  # failed twice, succeeded on the third


def test_gives_up_after_attempts_and_reraises():
    calls = {"n": 0}

    def always_timeout():
        calls["n"] += 1
        raise TimeoutError("read timed out")

    with pytest.raises(TimeoutError):
        with_retry(always_timeout, attempts=3)
    assert calls["n"] == 3  # bounded — exactly `attempts` tries, not infinite


def test_non_transient_error_is_not_retried():
    calls = {"n": 0}

    def bad_input():
        calls["n"] += 1
        raise ValueError("malformed schema")  # a real bug, not a network blip

    with pytest.raises(ValueError):
        with_retry(bad_input, attempts=5)
    assert calls["n"] == 1  # surfaced on the first try


def test_is_transient_classification():
    assert is_transient(ConnectionError("Connection reset by peer"))
    assert is_transient(Exception("HTTP 503 Service Unavailable"))
    assert is_transient(Exception("429 Too Many Requests"))
    assert is_transient(TimeoutError("timed out"))
    assert not is_transient(ValueError("bad value"))
    assert not is_transient(KeyError("missing"))


def test_passes_through_args_and_kwargs():
    def add(a, b, *, c=0):
        return a + b + c

    assert with_retry(add, 2, 3, c=4) == 9
