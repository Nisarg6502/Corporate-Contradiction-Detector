"""LLM contradiction judgment (config `judgment` model — gpt-oss:120b today).

Takes a candidate claim pair and returns {contradicts, severity, reasoning}.
Structured output with normalization (gpt-oss doesn't strictly honor schemas),
and a prompt tuned to avoid false positives — different *aspects* of a topic are
not contradictions.
"""

from __future__ import annotations

import json
import os
import re

_SEVERITIES = {"low", "medium", "high"}
_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "contradicts": {"type": "boolean"},
        "severity": {"type": "string", "enum": ["none", "low", "medium", "high"]},
        "reasoning": {"type": "string"},
    },
    "required": ["contradicts", "severity", "reasoning"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = (
    "You are a financial analyst detecting CONTRADICTIONS between two statements the "
    "same company (or its executives) made about the SAME topic, possibly at different "
    "times or in different documents (a real SEC filing vs a synthetic earnings-call "
    "excerpt).\n"
    "A CONTRADICTION means the two statements assert positions that cannot both be true: "
    "one affirms what the other denies, or they state opposite direction/magnitude on the "
    "same metric or risk.\n"
    "NOT contradictions: statements about different aspects of the topic, differences in "
    "emphasis or detail, or a general statement alongside a specific one that is consistent "
    "with it.\n"
    "Return: contradicts (bool); severity (none|low|medium|high — 'none' iff not a "
    "contradiction; 'high' = direct factual opposition on a material issue); reasoning "
    "(one sentence)."
)


def _period(pair, k) -> str:
    p = pair.get(k)
    return f", reporting period: {p}" if p else ""


def build_user(pair: dict) -> str:
    return (
        f"TOPIC: {pair['topic']}\n\n"
        f"STATEMENT A [{pair['a_source']} {pair['a_doctype']} {pair['a_date']}"
        f"{_period(pair, 'a_period')}, speaker: {pair['a_speaker']}]:\n"
        f"\"{pair['a_quote']}\"\n\n"
        f"STATEMENT B [{pair['b_source']} {pair['b_doctype']} {pair['b_date']}"
        f"{_period(pair, 'b_period')}, speaker: {pair['b_speaker']}]:\n"
        f"\"{pair['b_quote']}\"\n\n"
        "Note: a quarterly earnings call and the annual report for the same fiscal "
        "year describe the same reporting year. Do these two statements contradict "
        "each other on this topic?"
    )


def normalize_judgment(raw: dict) -> dict:
    contradicts = raw.get("contradicts")
    if contradicts is None:
        contradicts = raw.get("is_contradiction") or raw.get("contradiction") or False
    contradicts = bool(contradicts)
    severity = str(raw.get("severity", "none")).lower().strip()
    if not contradicts or severity not in _SEVERITIES:
        severity = "none" if not contradicts else "medium"
    reasoning = raw.get("reasoning") or raw.get("explanation") or ""
    return {"contradicts": contradicts, "severity": severity, "reasoning": reasoning}


def _parse(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        content = content.split("\n", 1)[1] if "\n" in content else content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = _JSON_OBJ.search(content)
        return json.loads(m.group(0)) if m else {}


def _ollama_usage(resp) -> dict | None:
    try:
        p, c = resp.get("prompt_eval_count"), resp.get("eval_count")
        if p is None and c is None:
            return None
        return {"input": p or 0, "output": c or 0, "total": (p or 0) + (c or 0)}
    except Exception:
        return None


def build_judge_call(cfg):
    j = cfg.models["judgment"]
    prov = cfg.models["providers"][j["provider"]]
    model = j["model"]
    temperature = j.get("temperature", 0.0)

    if prov["type"] == "ollama":
        from ollama import Client
        client = Client(host=os.environ.get(prov["host_env"], "https://ollama.com"),
                        headers={"Authorization": f"Bearer {os.environ[prov['api_key_env']]}"})

        def call(pair: dict) -> dict:
            from observability import obs
            from observability.retry import with_retry
            user = build_user(pair)
            with obs.generation("judge-contradiction", model,
                                prompt={"system": JUDGE_SYSTEM, "user": user},
                                metadata={"stage": "judgment", "topic": pair.get("topic")}) as gen:
                # Bounded retry: a transient Ollama free-tier failure would
                # otherwise drop one candidate pair's judgment.
                resp = with_retry(
                    client.chat, label="judge-contradiction",
                    model=model,
                    messages=[{"role": "system", "content": JUDGE_SYSTEM},
                              {"role": "user", "content": user}],
                    format=JUDGE_SCHEMA, options={"temperature": temperature})
                content = resp["message"]["content"]
                gen.finish(output=content, usage=_ollama_usage(resp))
            return normalize_judgment(_parse(content))

        call.model = model
        return call

    if prov["type"] == "vertex":
        from google import genai
        from google.genai import types
        client = genai.Client(vertexai=True,
                              project=os.environ[prov["project_env"]],
                              location=os.environ[prov["location_env"]])

        def call(pair: dict) -> dict:
            resp = client.models.generate_content(
                model=model, contents=build_user(pair),
                config=types.GenerateContentConfig(
                    system_instruction=JUDGE_SYSTEM, temperature=temperature,
                    response_mime_type="application/json", response_schema=JUDGE_SCHEMA))
            return normalize_judgment(_parse(resp.text or ""))

        call.model = model
        return call

    raise ValueError(f"Unknown provider type: {prov['type']}")
