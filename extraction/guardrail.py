"""Quote-span validation guardrail.

HARD CONSTRAINT (from the build plan): every stored claim must carry a
`quote_span` that is a verbatim substring of its source chunk. This module is
the enforcement point — any claim whose span can't be verified is rejected.

`recover_verbatim_span` tolerates only whitespace differences (the model
sometimes re-flows spaces), and when it matches it returns the *actual* substring
from the source so what we store is truly verbatim.
"""

from __future__ import annotations

import re


def recover_verbatim_span(source_text: str, span: str) -> str | None:
    """Return the exact substring of `source_text` matching `span`, or None.

    Exact match wins. Otherwise we retry allowing flexible whitespace only, and
    return the real matched slice so the stored span is verbatim to the source.
    """
    span = span.strip()
    if not span:
        return None
    if span in source_text:
        return span
    # Whitespace-flexible match: escape the span, collapse its whitespace to \s+.
    tokens = [re.escape(t) for t in span.split()]
    if not tokens:
        return None
    pattern = r"\s+".join(tokens)
    m = re.search(pattern, source_text)
    return m.group(0) if m else None


def validate_claims(source_text: str, raw_claims: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split raw claims into (valid, invalid).

    Valid claims get their `quote_span` normalized to the recovered verbatim
    slice. Invalid claims are those whose span isn't found in the source.
    """
    valid, invalid = [], []
    for c in raw_claims:
        recovered = recover_verbatim_span(source_text, c.get("quote_span", ""))
        if recovered is not None:
            c = {**c, "quote_span": recovered}
            valid.append(c)
        else:
            invalid.append(c)
    return valid, invalid
