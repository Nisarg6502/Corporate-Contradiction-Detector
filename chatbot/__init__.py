"""Conversational chatbot: LangGraph supervisor-orchestrator + agents.

Scoped to a single, already-processed company (ticker-locked tools) and
grounded strictly in that company's extracted claims and detected
contradictions — the same quote-span honesty guarantee the rest of the app is
built on. See `chatbot/graph.py` for the graph definition.
"""
