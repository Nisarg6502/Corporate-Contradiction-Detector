"""Qdrant vector store for claim embeddings (Cloud or self-hosted).

Points are keyed by a deterministic UUID derived from the claim_id (Qdrant point
ids must be int/UUID), with the claim_id + metadata carried in the payload so
graph enrichment can join back.
"""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (Distance, FieldCondition, Filter, MatchValue,
                                  PointStruct, VectorParams)

from config import get_config

_NS = uuid.UUID("6f9619ff-8b86-d011-b42d-00cf4fc964ff")  # fixed namespace


def get_client(cfg=None) -> QdrantClient:
    q = (cfg or get_config()).qdrant
    if q.get("url"):
        return QdrantClient(url=q["url"], api_key=q.get("api_key") or None)
    return QdrantClient(host=q["host"], port=int(q["port"]))


def point_id(claim_id: str) -> str:
    return str(uuid.uuid5(_NS, claim_id))


def ensure_collection(client: QdrantClient, name: str, dim: int) -> None:
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
    # Payload indexes are required before filtering on a field (Qdrant Cloud).
    for field in ("ticker", "topic", "source_type"):
        try:
            client.create_payload_index(name, field_name=field, field_schema="keyword")
        except Exception:
            pass  # already exists


def upsert_claims(client: QdrantClient, name: str, claims: list, vectors: list) -> int:
    points = []
    for c, vec in zip(claims, vectors):
        points.append(PointStruct(
            id=point_id(c.claim_id), vector=vec,
            payload={
                "claim_id": c.claim_id, "topic": c.topic, "speaker": c.speaker,
                "source_type": c.source_type, "date": c.date,
                "document_id": c.document_id, "ticker": c.company_ticker,
                "stance": c.stance, "quote_span": c.quote_span,
                "claim_text": c.claim_text,
            }))
    client.upsert(collection_name=name, points=points)
    return len(points)


def search(client: QdrantClient, name: str, query_vec: list, *, limit: int = 10,
           ticker: str | None = None) -> list[dict]:
    flt = None
    if ticker:
        flt = Filter(must=[FieldCondition(key="ticker", match=MatchValue(value=ticker))])
    resp = client.query_points(collection_name=name, query=query_vec,
                               limit=limit, query_filter=flt, with_payload=True)
    return [{"score": p.score, **p.payload} for p in resp.points]
