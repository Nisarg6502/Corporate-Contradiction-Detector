"""Input and output guardrails for the chat graph.

Two independent layers, on top of the ticker-lock in `chatbot/tools.py`:

- `input_guardrail` classifies the user's message *before* the orchestrator
  sees it, using the small/fast `guardrail` model (config `chat.guardrail`,
  default gpt-oss:20b). Off-scope, other-company, investment-advice, and
  injection attempts are short-circuited with canned copy from
  `config/chatbot.yaml` — never LLM-generated, so a jailbroken model can't
  spoof or suppress the refusal.
- `output_guardrail` checks the synthesizer's draft answer against what was
  actually retrieved this turn (grounding) and runs a small safety pass
  (advice/injection leakage). Both `llm` parameters are injectable so tests
  can run these functions without a network call.
"""

from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from config import get_config
from observability import obs

from .llm import build_chat_llm
from .prompts import INPUT_GUARDRAIL_SYSTEM, OUTPUT_SAFETY_SYSTEM

_VALID_CATEGORIES = ("other_company", "investment_advice", "off_topic", "injection", "ok")
# Matches a 16-hex claim_id right after "[", but does NOT require the "]" to
# follow immediately — the model sometimes annotates inside the same bracket
# (e.g. "[abc123... *synthetic*]") rather than writing a bare "[abc123...]".
# \b stops the match at the id boundary so it can't over-consume adjacent text.
_CITATION_RE = re.compile(r"\[([0-9a-f]{16})\b")
# gpt-oss models sometimes render bracketed citations with CJK full-width
# brackets instead of ASCII — normalize before matching rather than relying
# on prompt compliance for something this load-bearing.
_BRACKET_NORMALIZE = str.maketrans({"【": "[", "】": "]", "［": "[", "］": "]"})

_MAX_GUARDRAIL_RETRIES = 1


def _last_user_text(state: dict) -> str:
    for m in reversed(state.get("messages", [])):
        role = getattr(m, "type", None)
        if role in ("human", "user"):
            return m.content or ""
    return ""


def classify_input(text: str, company_name: str, ticker: str, llm=None) -> dict:
    """Pure classification helper — testable without going through graph state."""
    cfg = get_config()
    max_chars = cfg.chatbot.get("max_input_chars", 2000)
    if not text.strip():
        return {"category": "off_topic", "allowed": False, "reason": "empty message"}
    if len(text) > max_chars:
        return {"category": "off_topic", "allowed": False, "reason": "message too long"}

    llm = llm or build_chat_llm(cfg, "guardrail")
    model = cfg.models["chat"]["guardrail"]["model"]
    context = f"The company currently open is {company_name} ({ticker}).\n\nUser message: {text}"
    with obs.generation("chat-input-guardrail", model,
                         prompt={"system": INPUT_GUARDRAIL_SYSTEM, "user": context},
                         metadata={"ticker": ticker, "stage": "input_guardrail"}) as gen:
        resp = llm.invoke([SystemMessage(content=INPUT_GUARDRAIL_SYSTEM), HumanMessage(content=context)])
        gen.finish(output=resp.content)
    raw = (resp.content or "").strip().lower()
    category = next((c for c in _VALID_CATEGORIES if c in raw), "ok")
    return {"category": category, "allowed": category == "ok", "reason": raw}


def input_guardrail(state: dict) -> dict:
    text = _last_user_text(state)
    verdict = classify_input(text, state.get("company_name", ""), state.get("ticker", ""))
    return {"input_verdict": verdict}


def route_after_input_guardrail(state: dict) -> str:
    verdict = state.get("input_verdict") or {}
    return "orchestrator" if verdict.get("allowed") else "refuse"


def refusal_message(category: str) -> str:
    cfg = get_config()
    messages = cfg.chatbot.get("refusal_messages", {})
    return messages.get(category) or messages.get("off_topic", "I can't help with that.")


def extract_citations(text: str) -> set[str]:
    normalized = (text or "").translate(_BRACKET_NORMALIZE)
    return set(_CITATION_RE.findall(normalized))


def check_grounding(draft: str, retrieved: list[dict]) -> bool:
    """A draft is grounded if every citation marker it contains refers to a
    claim_id that was actually retrieved this turn. An answer with zero
    citations is trivially grounded (it isn't asserting anything specific to
    verify) — the safety pass below catches an *uncited* answer that smuggles
    advice or leaked instructions instead. A blank draft is NOT grounded —
    the synthesis model occasionally exhausts its token budget on internal
    reasoning before writing any content (see chatbot/llm.py), and an empty
    answer must trigger a retry/fallback rather than silently "passing"
    because it happens to contain zero citations."""
    if not draft.strip():
        return False
    cited = extract_citations(draft)
    if not cited:
        return True
    retrieved_ids = {r.get("claim_id") for r in retrieved if r.get("claim_id")}
    return cited.issubset(retrieved_ids)


def check_safety(draft: str, llm=None) -> bool:
    """Best-effort secondary check for advice/injection leakage in the draft.

    This is deliberately NOT the primary defense against investment advice or
    prompt injection — those are `input_guardrail` (blocks advice-seeking
    questions before the orchestrator ever runs) and the synthesis system
    prompt's explicit instruction. The small guardrail model is fast but
    unreliable at strict one-word formatting (empty responses, inconsistent
    phrasing even at temperature 0), so this check fails OPEN on an empty or
    ambiguous response rather than forcing a retry loop the model can't
    reliably resolve. It still catches the case it's good at: an explicit
    "unsafe" verdict on genuinely bad content."""
    cfg = get_config()
    llm = llm or build_chat_llm(cfg, "guardrail")
    model = cfg.models["chat"]["guardrail"]["model"]
    with obs.generation("chat-output-guardrail", model,
                         prompt={"system": OUTPUT_SAFETY_SYSTEM, "draft": draft},
                         metadata={"stage": "output_guardrail"}) as gen:
        resp = llm.invoke([SystemMessage(content=OUTPUT_SAFETY_SYSTEM), HumanMessage(content=draft)])
        gen.finish(output=resp.content)
    verdict = (resp.content or "").strip().lower()
    return "unsafe" not in verdict


def output_guardrail(state: dict) -> dict:
    draft = state.get("draft_answer", "")
    retrieved = state.get("retrieved", [])
    grounded = check_grounding(draft, retrieved) and check_safety(draft)
    retries = state.get("guardrail_retries", 0)

    if grounded:
        cited = extract_citations(draft)
        return {"answer": draft, "grounded": True, "cited_ids": sorted(cited)}

    if retries < _MAX_GUARDRAIL_RETRIES:
        return {"grounded": False, "guardrail_retries": retries + 1}

    return {"answer": refusal_message("ungrounded_fallback"), "grounded": True, "cited_ids": []}


def route_after_output_guardrail(state: dict) -> str:
    return "end" if state.get("grounded") else "synthesizer"
