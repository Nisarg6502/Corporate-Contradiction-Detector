"""Chatbot sanity checks (offline, network-free).

Covers the load-bearing guardrails: the ticker-lock in `chatbot/tools.py`
(the model can never query another company), the input/output guardrails in
`chatbot/guardrails.py` (scope/advice/injection classification, grounding
verification, citation-bracket normalization), pure graph routing, and the
session registry's ticker-mismatch behavior. LLM calls are stubbed with a
fake chat-model object — no network, no live Neo4j/Qdrant/Ollama required.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import AIMessage  # noqa: E402

from api import deps  # noqa: E402
from chatbot import guardrails, sessions  # noqa: E402
from chatbot.graph import route_after_orchestrator  # noqa: E402
from chatbot.tools import make_tools  # noqa: E402
from config import get_config  # noqa: E402


class _FakeLLM:
    """Duck-types the one method guardrails.py/tools call: .invoke(messages)."""

    def __init__(self, content: str):
        self.content = content
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return SimpleNamespace(content=self.content)


class _PoisonLLM:
    """Fails the test if invoked — for asserting a guardrail short-circuits
    before ever reaching the LLM."""

    def invoke(self, messages):
        raise AssertionError("LLM should not have been called")


class _FakeNeo4j:
    def __init__(self, rows=None):
        self.rows = rows if rows is not None else []
        self.calls = []

    def run(self, query, **params):
        self.calls.append((query, params))
        return self.rows


def _tool_call(tool, args, call_id="c1"):
    return tool.invoke({"type": "tool_call", "name": tool.name, "args": args, "id": call_id})


# ---------------------------------------------------------------------------
# Ticker-lock (chatbot/tools.py) — the primary guardrail
# ---------------------------------------------------------------------------

def test_make_tools_returns_expected_set():
    tools = make_tools("AAPL")
    names = {t.name for t in tools}
    assert names == {"list_topics", "get_claim_timeline", "get_contradictions",
                      "list_speakers", "semantic_search", "get_citation"}


def test_tools_never_expose_ticker_as_a_model_argument():
    # The model supplies tool args from the schema below — if "ticker" isn't
    # in it, the model has no way to ask for another company's data.
    for t in make_tools("AAPL"):
        schema = t.args_schema.model_json_schema() if hasattr(t.args_schema, "model_json_schema") else {}
        assert "ticker" not in schema.get("properties", {})


def test_list_topics_binds_the_session_ticker(monkeypatch):
    fake = _FakeNeo4j(rows=[{"topic": "gross_margin_profitability", "name": "Gross margin",
                              "description": "d", "claims": 3, "synthetic": 1}])
    monkeypatch.setattr(deps, "neo4j", lambda: fake)
    list_topics = next(t for t in make_tools("AAPL") if t.name == "list_topics")

    msg = _tool_call(list_topics, {})

    assert fake.calls[0][1]["ticker"] == "AAPL"
    assert msg.artifact == fake.rows
    assert "gross_margin_profitability" in msg.content


def test_get_claim_timeline_binds_ticker_and_forwards_topic(monkeypatch):
    fake = _FakeNeo4j(rows=[{"claim_id": "abc", "date": "2026-01-01", "speaker": "Company",
                              "role": "", "source": "real", "doc_type": "10-K",
                              "stance": "up", "quote": "text"}])
    monkeypatch.setattr(deps, "neo4j", lambda: fake)
    tool = next(t for t in make_tools("MSFT") if t.name == "get_claim_timeline")

    msg = _tool_call(tool, {"topic_id": "gross_margin_profitability"})

    _, params = fake.calls[0]
    assert params["ticker"] == "MSFT"
    assert params["topic"] == "gross_margin_profitability"
    assert "[abc]" in msg.content


def test_get_citation_rejects_claim_from_another_company(monkeypatch):
    fake = _FakeNeo4j(rows=[{"ok": False}])
    monkeypatch.setattr(deps, "neo4j", lambda: fake)
    tool = next(t for t in make_tools("AAPL") if t.name == "get_citation")

    msg = _tool_call(tool, {"claim_id": "someone-elses-claim"})

    assert msg.artifact == []
    assert "does not belong to this company" in msg.content
    assert fake.calls[0][1]["ticker"] == "AAPL"


def test_semantic_search_filters_qdrant_by_ticker(monkeypatch):
    import vector.embedder as embedder_mod
    import vector.qdrant_store as qdrant_mod

    monkeypatch.setattr(embedder_mod, "embed_one", lambda text: [0.0])
    captured = {}

    def fake_search(client, name, vec, *, limit=10, ticker=None):
        captured["ticker"] = ticker
        return [{"claim_id": "x1", "date": "2026-01-01", "speaker": "Company",
                  "source_type": "real", "topic": "t", "quote_span": "q"}]

    monkeypatch.setattr(qdrant_mod, "search", fake_search)
    monkeypatch.setattr(deps, "qdrant", lambda: object())
    monkeypatch.setattr(deps, "cfg", lambda: SimpleNamespace(qdrant={"claim_collection": "c"}))

    tool = next(t for t in make_tools("NVDA") if t.name == "semantic_search")
    msg = _tool_call(tool, {"query": "China exposure"})

    assert captured["ticker"] == "NVDA"
    assert "[x1]" in msg.content


# ---------------------------------------------------------------------------
# Input guardrail
# ---------------------------------------------------------------------------

def test_classify_input_short_circuits_on_empty_message():
    v = guardrails.classify_input("   ", "NVIDIA", "NVDA", llm=_PoisonLLM())
    assert v == {"category": "off_topic", "allowed": False, "reason": "empty message"}


def test_classify_input_short_circuits_on_length():
    long_text = "a" * 5000
    v = guardrails.classify_input(long_text, "NVIDIA", "NVDA", llm=_PoisonLLM())
    assert v["allowed"] is False and v["category"] == "off_topic"


def test_classify_input_uses_llm_verdict():
    v = guardrails.classify_input("Tell me about Apple", "NVIDIA", "NVDA",
                                   llm=_FakeLLM("other_company"))
    assert v == {"category": "other_company", "allowed": False, "reason": "other_company"}


def test_classify_input_ok_allows_through():
    v = guardrails.classify_input("What did they say about margins?", "NVIDIA", "NVDA",
                                   llm=_FakeLLM("ok"))
    assert v["allowed"] is True and v["category"] == "ok"


def test_classify_input_defaults_to_ok_on_unrecognized_output():
    v = guardrails.classify_input("hello", "NVIDIA", "NVDA", llm=_FakeLLM("banana"))
    assert v["category"] == "ok"


def test_route_after_input_guardrail():
    assert guardrails.route_after_input_guardrail({"input_verdict": {"allowed": True}}) == "orchestrator"
    assert guardrails.route_after_input_guardrail({"input_verdict": {"allowed": False}}) == "refuse"
    assert guardrails.route_after_input_guardrail({}) == "refuse"


def test_refusal_message_known_category_and_fallback():
    msg = guardrails.refusal_message("investment_advice")
    assert "advice" in msg.lower()
    # unknown category falls back to off_topic copy rather than crashing
    assert guardrails.refusal_message("nonsense") == guardrails.refusal_message("off_topic")


# ---------------------------------------------------------------------------
# Output guardrail: citation extraction + grounding + safety
# ---------------------------------------------------------------------------

def test_extract_citations_normalizes_fullwidth_brackets():
    text = "Margin improved 【dee3759a1696f01e】 per the filing."
    assert guardrails.extract_citations(text) == {"dee3759a1696f01e"}


def test_extract_citations_ascii():
    text = "See [ff69ebfbea2b65b5] and [dee3759a1696f01e]."
    assert guardrails.extract_citations(text) == {"ff69ebfbea2b65b5", "dee3759a1696f01e"}


def test_check_grounding_true_when_no_citations():
    assert guardrails.check_grounding("I don't have that in the filings.", []) is True


def test_check_grounding_true_when_cited_ids_were_retrieved():
    retrieved = [{"claim_id": "dee3759a1696f01e"}, {"a_id": "x", "b_id": "y"}]
    draft = "Margin improved [dee3759a1696f01e]."
    assert guardrails.check_grounding(draft, retrieved) is True


def test_check_grounding_false_on_fabricated_citation():
    retrieved = [{"claim_id": "dee3759a1696f01e"}]
    draft = "Margin improved [0000000000000000]."
    assert guardrails.check_grounding(draft, retrieved) is False


def test_check_safety_flags_explicit_unsafe():
    assert guardrails.check_safety("draft", llm=_FakeLLM("unsafe")) is False


def test_check_safety_fails_open_on_ambiguous_or_empty_output():
    assert guardrails.check_safety("draft", llm=_FakeLLM("")) is True
    assert guardrails.check_safety("draft", llm=_FakeLLM("This looks fine.")) is True


def test_output_guardrail_accepts_grounded_safe_draft(monkeypatch):
    monkeypatch.setattr(guardrails, "build_chat_llm", lambda cfg, role: _FakeLLM("safe"))
    state = {"draft_answer": "Margin improved [dee3759a1696f01e].",
             "retrieved": [{"claim_id": "dee3759a1696f01e"}], "guardrail_retries": 0}
    result = guardrails.output_guardrail(state)
    assert result["grounded"] is True
    assert result["cited_ids"] == ["dee3759a1696f01e"]
    assert result["answer"] == state["draft_answer"]


def test_output_guardrail_retries_once_then_falls_back(monkeypatch):
    monkeypatch.setattr(guardrails, "build_chat_llm", lambda cfg, role: _FakeLLM("unsafe"))
    state = {"draft_answer": "Margin improved [0000000000000000].",
             "retrieved": [], "guardrail_retries": 0}

    first = guardrails.output_guardrail(state)
    assert first["grounded"] is False
    assert first["guardrail_retries"] == 1

    state["guardrail_retries"] = 1
    second = guardrails.output_guardrail(state)
    assert second["grounded"] is True
    assert second["cited_ids"] == []
    assert second["answer"] == guardrails.refusal_message("ungrounded_fallback")


def test_route_after_output_guardrail():
    assert guardrails.route_after_output_guardrail({"grounded": True}) == "end"
    assert guardrails.route_after_output_guardrail({"grounded": False}) == "synthesizer"


# ---------------------------------------------------------------------------
# Graph routing (pure, no LLM)
# ---------------------------------------------------------------------------

def test_route_after_orchestrator_with_tool_calls():
    msg = AIMessage(content="", tool_calls=[
        {"name": "list_topics", "args": {}, "id": "1", "type": "tool_call"}])
    assert route_after_orchestrator({"messages": [msg]}) == "tools"


def test_route_after_orchestrator_without_tool_calls():
    msg = AIMessage(content="all done")
    assert route_after_orchestrator({"messages": [msg]}) == "synthesizer"


# ---------------------------------------------------------------------------
# Session registry: ticker-mismatch always starts a fresh, correctly-scoped
# session (the second half of the ticker-lock guarantee).
# ---------------------------------------------------------------------------

def test_get_or_create_reuses_matching_session(monkeypatch):
    monkeypatch.setattr(sessions, "build_chat_graph",
                         lambda ticker, name, checkpointer=None: f"graph-{ticker}")
    s1 = sessions.get_or_create(None, "AAPL", "Apple")
    s2 = sessions.get_or_create(s1["session_id"], "AAPL", "Apple")
    assert s2["session_id"] == s1["session_id"]


def test_get_or_create_ticker_mismatch_starts_new_session(monkeypatch):
    monkeypatch.setattr(sessions, "build_chat_graph",
                         lambda ticker, name, checkpointer=None: f"graph-{ticker}")
    s1 = sessions.get_or_create(None, "AAPL", "Apple")
    s2 = sessions.get_or_create(s1["session_id"], "MSFT", "Microsoft")
    assert s2["session_id"] != s1["session_id"]
    assert s2["ticker"] == "MSFT"
    assert s2["graph"] == "graph-MSFT"


def test_record_turn_rate_limits(monkeypatch):
    monkeypatch.setattr(sessions, "build_chat_graph",
                         lambda ticker, name, checkpointer=None: "graph")
    sid = sessions.start_session("AAPL", "Apple")
    limit = get_config().chatbot.get("rate_limit_per_minute", 20)
    for _ in range(limit):
        assert sessions.record_turn(sid) is True
    assert sessions.record_turn(sid) is False
