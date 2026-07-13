"""Text embeddings via FastEmbed (ONNX, CPU, no torch)."""

from __future__ import annotations

import os
from functools import lru_cache

from config import get_config


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding
    # FASTEMBED_CACHE_DIR lets the Docker image bake the ONNX model into a
    # persistent path (Cloud Run mounts /tmp as an empty tmpfs, so fastembed's
    # default /tmp cache would be lost at runtime). Unset locally -> default.
    cache_dir = os.getenv("FASTEMBED_CACHE_DIR") or None
    return TextEmbedding(
        model_name=get_config().models["embedding"]["model"], cache_dir=cache_dir
    )


def embed(texts: list[str]) -> list[list[float]]:
    return [list(map(float, v)) for v in _model().embed(list(texts))]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
