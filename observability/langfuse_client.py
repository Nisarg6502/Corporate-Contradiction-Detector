"""Langfuse Cloud tracing with a no-op fallback.

If LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are absent (or the SDK errors), every
call here is a silent no-op, so the pipeline, API, and tests run unconfigured.

Usage:
    from observability import obs
    with obs.run("process-company", ticker="AAPL"):        # parent trace/span
        with obs.generation("extract-chunk", model, prompt, meta) as gen:
            resp = client.chat(...)
            gen.finish(output=text, usage={"input": p, "output": c})
    obs.flush()
"""

from __future__ import annotations

import contextlib
import os
import sys

_client = None
_state = "uninitialized"  # -> "on" | "off"


def _init():
    global _client, _state
    if _state != "uninitialized":
        return
    pk, sk = os.environ.get("LANGFUSE_PUBLIC_KEY"), os.environ.get("LANGFUSE_SECRET_KEY")
    if not (pk and sk):
        _state = "off"
        return
    try:
        from langfuse import Langfuse
        _client = Langfuse(public_key=pk, secret_key=sk,
                           host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"))
        _state = "on"
    except Exception:
        _state = "off"


def is_enabled() -> bool:
    _init()
    return _state == "on"


class _Gen:
    """Handle to record output/usage on a generation. No-op when obj is None."""

    def __init__(self, obj):
        self._obj = obj

    def finish(self, *, output=None, usage=None, metadata=None) -> None:
        if self._obj is None:
            return
        kw = {}
        if output is not None:
            kw["output"] = output
        if usage is not None:
            kw["usage_details"] = usage
        if metadata is not None:
            kw["metadata"] = metadata
        try:
            self._obj.update(**kw)
        except Exception:
            pass


@contextlib.contextmanager
def _observe(as_type: str, name: str, wrap, **kw):
    """Yield `wrap(obj)` inside a Langfuse observation, guaranteeing exactly one
    yield. Tracing failures degrade to a no-op, and — critically — exceptions from
    the wrapped block propagate normally (they are NOT swallowed with a second
    yield, which would raise 'generator didn't stop after throw()')."""
    cm = obj = None
    try:
        cm = _client.start_as_current_observation(name=name, as_type=as_type, **kw)
        obj = cm.__enter__()
    except Exception:
        cm = None
    try:
        yield wrap(obj)
    finally:
        if cm is not None:
            try:
                cm.__exit__(*sys.exc_info())
            except Exception:
                pass


def run(name: str, **metadata):
    """Parent span grouping all generations for one pipeline run."""
    if not is_enabled():
        return contextlib.nullcontext(None)
    return _observe("chain", name, lambda o: o, input=metadata, metadata=metadata)


def generation(name: str, model: str, prompt, metadata=None):
    """A single LLM call; timing is captured by the context span."""
    if not is_enabled():
        return contextlib.nullcontext(_Gen(None))
    return _observe("generation", name, _Gen, input=prompt, model=model,
                    metadata=metadata or {})


def flush() -> None:
    if is_enabled():
        try:
            _client.flush()
        except Exception:
            pass
