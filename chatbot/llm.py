"""Provider-agnostic LLM factory for the chatbot (config `chat.<role>`).

Mirrors the dispatch pattern in `detection/judge.py:build_judge_call` and
`extraction/providers.py:make_llm_call` — provider/model selection is
config-driven, never hardcoded. Unlike those (which use the raw `ollama`
client for one-shot structured calls), the chatbot needs LangGraph's
tool-binding + streaming, so this returns a LangChain chat model instead.

`role` is one of "orchestrator", "synthesis", "guardrail" (see
`config/models.yaml` -> chat).
"""

from __future__ import annotations

import os

ROLES = ("orchestrator", "synthesis", "guardrail")


def _ollama_chat(role_cfg: dict, prov: dict):
    from langchain_ollama import ChatOllama

    host = os.environ.get(prov["host_env"], "https://ollama.com")
    api_key = os.environ[prov["api_key_env"]]
    return ChatOllama(
        model=role_cfg["model"],
        base_url=host,
        temperature=role_cfg.get("temperature", 0.0),
        num_predict=role_cfg.get("max_tokens", 2048),
        # gpt-oss models reason internally before answering (a separate
        # "thinking" field, not `content`); for a fast yes/no classifier that
        # reasoning is unnecessary and — worse — can consume the whole token
        # budget before any `content` is emitted. `reasoning` maps straight to
        # Ollama's `think` param; leave it unset (model default: on) for
        # roles that benefit from chain-of-thought, like orchestration and
        # synthesis.
        reasoning=role_cfg.get("reasoning", None),
        client_kwargs={"headers": {"Authorization": f"Bearer {api_key}"}},
    )


def _vertex_chat(role_cfg: dict, prov: dict):
    from langchain_google_vertexai import ChatVertexAI

    return ChatVertexAI(
        model=role_cfg["model"],
        project=os.environ[prov["project_env"]],
        location=os.environ[prov["location_env"]],
        temperature=role_cfg.get("temperature", 0.0),
        max_output_tokens=role_cfg.get("max_tokens", 2048),
    )


def build_chat_llm(cfg, role: str):
    """Build the LangChain chat model for one chat role.

    `cfg.models["chat"][role]` names its own provider (a role can run on a
    different backend than another), falling back to the top-level
    `chat.provider` if set for backward-compat with a flatter config shape.
    """
    if role not in ROLES:
        raise ValueError(f"Unknown chat role: {role!r} (expected one of {ROLES})")
    chat_cfg = cfg.models["chat"]
    role_cfg = chat_cfg[role]
    provider_name = role_cfg.get("provider") or chat_cfg.get("provider")
    prov = cfg.models["providers"][provider_name]
    ptype = prov["type"]
    if ptype == "ollama":
        return _ollama_chat(role_cfg, prov)
    if ptype == "vertex":
        return _vertex_chat(role_cfg, prov)
    raise ValueError(f"Unknown provider type: {ptype}")
