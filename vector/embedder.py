"""Text embeddings via FastEmbed (ONNX, CPU, no torch)."""

from __future__ import annotations

from functools import lru_cache

from config import get_config


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=get_config().models["embedding"]["model"])


def embed(texts: list[str]) -> list[list[float]]:
    return [list(map(float, v)) for v in _model().embed(list(texts))]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
