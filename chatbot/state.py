"""Shared LangGraph state for one chat turn.

`messages` carries the LangChain conversation history (persisted across turns
by the graph's checkpointer, keyed by thread_id = session_id). Every other
field is turn-scoped bookkeeping the graph nodes pass to each other.
"""

from __future__ import annotations

from typing import Annotated, Optional, TypedDict

from langgraph.graph.message import add_messages


class ChatState(TypedDict, total=False):
    messages: Annotated[list, add_messages]

    # Session identity — set once per session, never mutated by the LLM.
    ticker: str
    company_name: str

    # Input guardrail verdict for this turn.
    # allowed: bool; category: "ok" | "off_topic" | "other_company"
    #   | "investment_advice" | "injection"; reason: str
    input_verdict: Optional[dict]

    # Context the orchestrator's tools have retrieved this turn — each item
    # carries at least {claim_id, source_type} so the output guardrail can
    # verify grounding.
    retrieved: list[dict]

    # claim_ids the final answer actually cites (subset of `retrieved`).
    cited_ids: list[str]

    # Number of orchestrator tool-call rounds used this turn (bounded by
    # config/chatbot.yaml: max_tool_iterations).
    tool_iterations: int

    # Number of synthesis regenerations attempted after a failed grounding/
    # safety check (bounded to 1 retry before falling back to a canned reply).
    guardrail_retries: int

    # Final answer text, pre- and post-guardrail.
    draft_answer: str
    answer: str

    # Set when the output guardrail can't verify grounding after one retry.
    grounded: bool
