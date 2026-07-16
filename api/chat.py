"""Chat endpoints: the conversational assistant scoped to one open company.

  POST /companies/{ticker}/chat              -> SSE stream of the chat turn
  GET  /companies/{ticker}/chat/suggestions   -> starter questions
  GET  /companies/{ticker}/summary            -> SSE stream of an executive summary

Streaming uses FastAPI's built-in `StreamingResponse` over `text/event-stream`
(no extra dependency) rather than a websocket, matching the rest of the app's
minimal-deps approach. Every turn is scoped to an already-processed ticker —
unprocessed companies get a 400, same as the rest of the API.
"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api import deps
from observability import obs

# langgraph/langchain_ollama (via chatbot.*) are heavy imports only the chat
# endpoints need — deferred into each handler below so a cold Cloud Run
# container doesn't pay that import cost just to serve landing/browsing
# routes, which never touch this router's handlers.

router = APIRouter()

_MAX_MESSAGE_CHARS = 8000  # hygiene ceiling; the semantic input guardrail is stricter


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class FollowupRequest(BaseModel):
    question: str
    answer: str


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _require_processed(ticker: str) -> str:
    ticker = ticker.upper()
    if ticker not in deps.processed_tickers():
        raise HTTPException(400, f"{ticker} has not been processed yet")
    return ticker


async def _sse_chat_stream(session: dict, message: str) -> AsyncIterator[str]:
    from langchain_core.messages import HumanMessage
    graph = session["graph"]
    session_id = session["session_id"]
    ticker = session["ticker"]
    cfg = deps.cfg()
    config = {"configurable": {"thread_id": session_id}, "recursion_limit": 60}
    input_state = {
        "messages": [HumanMessage(content=message)],
        "ticker": ticker,
        "company_name": session["company_name"],
        "tool_iterations": 0,
        "guardrail_retries": 0,
    }

    yield _sse("session", {"session_id": session_id})

    streamed_any = False
    current_synth_run_id = None
    timeout_s = cfg.chatbot.get("turn_timeout_seconds", 60)

    with obs.run("chat-turn", ticker=ticker, session_id=session_id):
        try:
            async with asyncio.timeout(timeout_s):
                async for event in graph.astream_events(input_state, config=config, version="v2"):
                    kind = event["event"]
                    node = (event.get("metadata") or {}).get("langgraph_node")

                    if kind == "on_chat_model_start" and node == "synthesizer":
                        if current_synth_run_id is not None:
                            # A guardrail retry restarted synthesis — tell the
                            # client to discard whatever it streamed so far.
                            yield _sse("retry", {})
                            streamed_any = False
                        current_synth_run_id = event.get("run_id")
                    elif kind == "on_chat_model_stream" and node == "synthesizer":
                        text = getattr(event["data"]["chunk"], "content", "") or ""
                        if text:
                            streamed_any = True
                            yield _sse("token", {"text": text})
                    elif kind == "on_tool_start" and node == "tools":
                        yield _sse("tool", {"name": event.get("name"), "status": "start"})
                    elif kind == "on_tool_end" and node == "tools":
                        yield _sse("tool", {"name": event.get("name"), "status": "end"})

                snapshot = await graph.aget_state(config)
        except TimeoutError:
            yield _sse("error", {"message": "This is taking too long — please try again."})
            yield _sse("done", {"answer": "", "cited_ids": [], "session_id": session_id})
            return
        except Exception:
            yield _sse("error", {"message": "Something went wrong answering that — please try again."})
            yield _sse("done", {"answer": "", "cited_ids": [], "session_id": session_id})
            return

    values = snapshot.values
    answer = values.get("answer", "")
    cited_ids = values.get("cited_ids", [])

    if not streamed_any and answer:
        yield _sse("token", {"text": answer})

    yield _sse("citation", {"claim_ids": cited_ids})
    yield _sse("done", {"answer": answer, "cited_ids": cited_ids, "session_id": session_id})


@router.post("/companies/{ticker}/chat")
async def chat(ticker: str, body: ChatRequest):
    from chatbot import sessions
    ticker = _require_processed(ticker)
    if len(body.message) > _MAX_MESSAGE_CHARS:
        raise HTTPException(400, "message too long")
    if not body.message.strip():
        raise HTTPException(400, "message is empty")

    company_name = deps.company_name(ticker) or ticker
    session = sessions.get_or_create(body.session_id, ticker, company_name)
    if not sessions.record_turn(session["session_id"]):
        raise HTTPException(429, "Too many messages — please slow down.")

    return StreamingResponse(
        _sse_chat_stream(session, body.message),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/companies/{ticker}/chat/suggestions")
def chat_suggestions(ticker: str):
    from chatbot import suggestions
    ticker = _require_processed(ticker)
    return {"questions": suggestions.suggested_questions(ticker)}


@router.post("/companies/{ticker}/chat/followups")
def chat_followups(ticker: str, body: FollowupRequest):
    """Contextual follow-up questions for the just-finished turn. Called after
    the answer has streamed, so it never delays the answer. Best-effort — an
    empty list is a fine result, the UI just shows no chips."""
    from chatbot import suggestions
    ticker = _require_processed(ticker)
    company_name = deps.company_name(ticker) or ticker
    questions = suggestions.followup_questions(ticker, company_name, body.question, body.answer)
    return {"questions": questions}


@router.get("/companies/{ticker}/summary")
async def company_summary(ticker: str):
    from chatbot import guardrails, summary
    ticker = _require_processed(ticker)
    company_name = deps.company_name(ticker) or ticker

    async def _stream() -> AsyncIterator[str]:
        full_text = []
        timeout_s = deps.cfg().chatbot.get("turn_timeout_seconds", 60)
        try:
            with obs.run("chat-summary-stream", ticker=ticker):
                async with asyncio.timeout(timeout_s):
                    async for chunk in summary.astream_executive_summary(ticker, company_name):
                        full_text.append(chunk)
                        yield _sse("token", {"text": chunk})
        except TimeoutError:
            yield _sse("error", {"message": "This is taking too long — please try again."})
            yield _sse("done", {})
            return
        except Exception:
            yield _sse("error", {"message": "Something went wrong loading the summary — please try again."})
            yield _sse("done", {})
            return
        cited_ids = sorted(guardrails.extract_citations("".join(full_text)))
        yield _sse("citation", {"claim_ids": cited_ids})
        yield _sse("done", {})

    return StreamingResponse(
        _stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
