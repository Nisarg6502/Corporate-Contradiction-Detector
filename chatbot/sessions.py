"""In-process chat session registry, mirroring `api/jobs.py`'s pattern.

A session binds one `session_id` to one ticker's compiled chat graph, so
conversation state (via the graph's checkpointer) persists across follow-up
turns. Sessions are held in memory for the life of the API process — fine for
a single-instance deployment; a multi-worker deployment would need a shared
store instead (out of scope here, matching the existing job registry).
"""

from __future__ import annotations

import threading
import time
import uuid

from langgraph.checkpoint.memory import MemorySaver

from config import get_config

from .graph import build_chat_graph

_sessions: dict[str, dict] = {}
_lock = threading.Lock()

# One checkpointer shared across every session's compiled graph — checkpoints
# are keyed by thread_id (= session_id) at call time, so sharing it is safe
# and avoids a per-session memory store.
_checkpointer = MemorySaver()


def start_session(ticker: str, company_name: str) -> str:
    """Create a new session bound to one ticker; returns its session_id."""
    session_id = uuid.uuid4().hex[:16]
    graph = build_chat_graph(ticker, company_name, checkpointer=_checkpointer)
    with _lock:
        _sessions[session_id] = {
            "session_id": session_id,
            "ticker": ticker,
            "company_name": company_name,
            "graph": graph,
            "created_at": time.time(),
        }
    return session_id


def get_session(session_id: str) -> dict | None:
    with _lock:
        s = _sessions.get(session_id)
        return dict(s) if s else None


def get_or_create(session_id: str | None, ticker: str, company_name: str) -> dict:
    """Return the session for `session_id` if it exists and is bound to
    `ticker`; otherwise start a fresh one. A ticker mismatch (e.g. a client
    reusing a session_id from a different company's chat) always starts a new,
    correctly-scoped session rather than silently answering with the wrong
    company's tools — this is the session-level half of the ticker-lock
    guardrail (`chatbot/tools.py` is the tool-level half)."""
    if session_id:
        existing = get_session(session_id)
        if existing and existing["ticker"] == ticker:
            return existing
    new_id = start_session(ticker, company_name)
    return get_session(new_id)


def record_turn(session_id: str) -> bool:
    """Record a turn against the session's rolling rate limit; returns False
    if the session should be throttled (config `chatbot.rate_limit_per_minute`)."""
    limit = get_config().chatbot.get("rate_limit_per_minute", 20)
    now = time.time()
    with _lock:
        s = _sessions.get(session_id)
        if s is None:
            return True
        turns = [t for t in s.get("turns", []) if now - t < 60]
        if len(turns) >= limit:
            s["turns"] = turns
            return False
        turns.append(now)
        s["turns"] = turns
        return True
