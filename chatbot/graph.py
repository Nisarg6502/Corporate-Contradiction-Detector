"""The chat supervisor graph.

    START -> input_guardrail --(reject)--> refuse -> END
                    |
                (allowed)
                    v
              orchestrator <---------------------.
                    |                              |
           (tool_calls?)                      collect_retrieved
              yes |  \ no                           ^
                  v   \                              |
                tools  `--------------------------.  |
                  |                                |  |
                  `--------------------------------'--'
                                                    |
                                              synthesizer
                                                    |
                                            output_guardrail
                                            /              \\
                                   (ungrounded)          (grounded)
                                        |                     |
                                  synthesizer (retry)         END

`orchestrator` and `tools` loop until the model stops requesting tools (or
hits `max_tool_iterations`, at which point it's invoked without tools bound so
it's forced to stop). `synthesizer` writes the final grounded answer from
whatever `tools` retrieved; `output_guardrail` verifies grounding/safety and
either accepts the answer or sends it back for one retry, else falls back to a
canned "not in the filings" reply.

Everything here is scoped to one (ticker, company_name) pair via
`chatbot.tools.make_tools` — see that module for the ticker-lock guarantee.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from config import get_config
from observability import obs

from . import guardrails
from .llm import build_chat_llm
from .prompts import SYNTHESIS_SYSTEM, orchestrator_system
from .state import ChatState
from .tools import make_tools


def route_after_orchestrator(state: ChatState) -> str:
    """Pure routing function (no closure state) — testable in isolation."""
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else "synthesizer"


def build_chat_graph(ticker: str, company_name: str, checkpointer=None):
    cfg = get_config()
    tools = make_tools(ticker)
    tool_node = ToolNode(tools)

    orchestrator_model = cfg.models["chat"]["orchestrator"]["model"]
    synthesis_model = cfg.models["chat"]["synthesis"]["model"]
    base_orchestrator_llm = build_chat_llm(cfg, "orchestrator")
    orchestrator_llm_with_tools = base_orchestrator_llm.bind_tools(tools)
    synthesis_llm = build_chat_llm(cfg, "synthesis")

    max_iterations = cfg.chatbot.get("max_tool_iterations", 6)
    sys_orchestrator = SystemMessage(content=orchestrator_system(company_name, ticker))
    sys_synthesis = SystemMessage(content=SYNTHESIS_SYSTEM)

    def orchestrator_node(state: ChatState) -> dict:
        iterations = state.get("tool_iterations", 0)
        # Once the budget is spent, invoke without tools bound so the model is
        # forced to stop requesting them instead of leaving a dangling
        # unresolved tool_call in the history.
        llm = orchestrator_llm_with_tools if iterations < max_iterations else base_orchestrator_llm
        messages = [sys_orchestrator, *state["messages"]]
        with obs.generation("chat-orchestrator", orchestrator_model,
                             prompt={"system": sys_orchestrator.content, "turn": iterations},
                             metadata={"ticker": ticker, "stage": "orchestrator"}) as gen:
            resp = llm.invoke(messages)
            gen.finish(output=resp.content, usage=_usage(resp))
        return {"messages": [resp], "tool_iterations": iterations + 1}

    def collect_retrieved_node(state: ChatState) -> dict:
        retrieved: list[dict] = []
        for m in state["messages"]:
            if isinstance(m, ToolMessage) and getattr(m, "artifact", None):
                retrieved.extend(m.artifact)
        return {"retrieved": retrieved}

    def synthesizer_node(state: ChatState) -> dict:
        # Drop the orchestrator's own freeform commentary: when it decides
        # it's done, it sometimes writes prose alongside stopping instead of
        # emitting bare tool_calls. Left in, the synthesis model treats the
        # question as already answered and just tacks on a trailing remark
        # instead of writing the real cited answer. Tool-call-only AIMessages
        # have no content anyway, so this only ever strips that stray prose.
        history = [
            m for m in state["messages"]
            if not (isinstance(m, AIMessage) and not getattr(m, "tool_calls", None))
        ]
        messages = [sys_synthesis, *history]
        with obs.generation("chat-synthesis", synthesis_model,
                             prompt={"system": SYNTHESIS_SYSTEM},
                             metadata={"ticker": ticker, "stage": "synthesis",
                                       "retry": state.get("guardrail_retries", 0)}) as gen:
            resp = synthesis_llm.invoke(messages)
            gen.finish(output=resp.content, usage=_usage(resp))
        return {"draft_answer": resp.content}

    def output_guardrail_node(state: ChatState) -> dict:
        result = guardrails.output_guardrail(state)
        if result.get("grounded"):
            result = {**result, "messages": [AIMessage(content=result["answer"])]}
        return result

    def refuse_node(state: ChatState) -> dict:
        category = (state.get("input_verdict") or {}).get("category", "off_topic")
        text = guardrails.refusal_message(category)
        return {"answer": text, "cited_ids": [], "messages": [AIMessage(content=text)]}

    g = StateGraph(ChatState)
    g.add_node("input_guardrail", guardrails.input_guardrail)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("tools", tool_node)
    g.add_node("collect_retrieved", collect_retrieved_node)
    g.add_node("synthesizer", synthesizer_node)
    g.add_node("output_guardrail", output_guardrail_node)
    g.add_node("refuse", refuse_node)

    g.add_edge(START, "input_guardrail")
    g.add_conditional_edges(
        "input_guardrail", guardrails.route_after_input_guardrail,
        {"orchestrator": "orchestrator", "refuse": "refuse"})
    g.add_edge("refuse", END)
    g.add_conditional_edges(
        "orchestrator", route_after_orchestrator,
        {"tools": "tools", "synthesizer": "synthesizer"})
    g.add_edge("tools", "collect_retrieved")
    g.add_edge("collect_retrieved", "orchestrator")
    g.add_edge("synthesizer", "output_guardrail")
    g.add_conditional_edges(
        "output_guardrail", guardrails.route_after_output_guardrail,
        {"end": END, "synthesizer": "synthesizer"})

    return g.compile(checkpointer=checkpointer)


def _usage(resp) -> dict | None:
    meta = getattr(resp, "usage_metadata", None)
    if not meta:
        return None
    return {"input": meta.get("input_tokens", 0), "output": meta.get("output_tokens", 0),
            "total": meta.get("total_tokens", 0)}
