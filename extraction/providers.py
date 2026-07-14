"""Provider-agnostic LLM call for extraction.

`make_llm_call(cfg)` reads `cfg.models["extraction"]` + the provider registry and
returns a closure `call(system, user, topic_ids) -> list[dict]`. Backends are
selected purely from config (Ollama Cloud today; Vertex/Gemini once its API is
enabled), honoring the plan's "model choice is config-driven" rule. Both use
strict/structured JSON output derived from the same tool schema.
"""

from __future__ import annotations

import json
import os
import re

from .schema import build_extraction_tool

_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def _parse_claims(content: str) -> list[dict]:
    """Parse the model's JSON, tolerating code fences / stray prose."""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content.split("\n", 1)[1] if "\n" in content else content
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        m = _JSON_OBJ.search(content)
        if not m:
            return []
        data = json.loads(m.group(0))
    # Accept either {"claims": [...]} or a bare [...] of claims.
    if isinstance(data, dict):
        return list(data.get("claims", []))
    if isinstance(data, list):
        return data
    return []


def _make_ollama_call(prov, ex):
    from ollama import Client

    host = os.environ.get(prov["host_env"], "https://ollama.com")
    api_key = os.environ[prov["api_key_env"]]
    client = Client(host=host, headers={"Authorization": f"Bearer {api_key}"})
    model = ex["model"]
    temperature = ex.get("temperature", 0.0)

    def call(system: str, user: str, topic_ids: list[str]) -> list[dict]:
        from observability import obs
        from observability.retry import with_retry
        schema = build_extraction_tool(topic_ids)["input_schema"]
        with obs.generation("extract-claims", model,
                            prompt={"system": system, "user": user},
                            metadata={"stage": "extraction"}) as gen:
            # Bounded retry: Ollama's free tier intermittently times out / 503s;
            # one blip would otherwise drop a chunk's claims for the whole run.
            resp = with_retry(
                client.chat, label="extract-claims",
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                format=schema,                  # structured output, schema-constrained
                options={"temperature": temperature},
            )
            content = resp["message"]["content"]
            gen.finish(output=content, usage=_ollama_usage(resp))
        return _parse_claims(content)

    call.model = model
    return call


def _ollama_usage(resp) -> dict | None:
    """Map Ollama token counts to Langfuse usage_details."""
    try:
        p, c = resp.get("prompt_eval_count"), resp.get("eval_count")
        if p is None and c is None:
            return None
        return {"input": p or 0, "output": c or 0, "total": (p or 0) + (c or 0)}
    except Exception:
        return None


def _make_vertex_call(prov, ex):
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True,
                          project=os.environ[prov["project_env"]],
                          location=os.environ[prov["location_env"]])
    model = ex["model"]
    temperature = ex.get("temperature", 0.0)

    def call(system: str, user: str, topic_ids: list[str]) -> list[dict]:
        schema = build_extraction_tool(topic_ids)["input_schema"]
        resp = client.models.generate_content(
            model=model, contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system, temperature=temperature,
                response_mime_type="application/json", response_schema=schema),
        )
        return _parse_claims(resp.text or "")

    call.model = model
    return call


def make_llm_call(cfg):
    ex = cfg.models["extraction"]
    prov = cfg.models["providers"][ex["provider"]]
    ptype = prov["type"]
    if ptype == "ollama":
        return _make_ollama_call(prov, ex)
    if ptype == "vertex":
        return _make_vertex_call(prov, ex)
    raise ValueError(f"Unknown provider type: {ptype}")
