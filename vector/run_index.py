"""Index all extracted claims into Qdrant for hybrid search (Checkpoint 6).

    python -m vector.run_index

Embeds each claim (claim_text + quote_span) with FastEmbed and upserts to the
claim_embeddings collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config              # noqa: E402
from extraction import claim_store          # noqa: E402
from vector import embedder, qdrant_store   # noqa: E402


def index_company(ticker: str, *, cfg=None) -> int:
    """Embed + upsert just one company's claims into Qdrant."""
    cfg = cfg or get_config()
    coll = cfg.qdrant["claim_collection"]
    dim = int(cfg.models["embedding"]["dimension"])
    claims = [c for c in claim_store.load_claims().values()
              if c.company_ticker == ticker]
    if not claims:
        return 0
    texts = [f"{c.claim_text} {c.quote_span}".strip() for c in claims]
    vectors = embedder.embed(texts)
    client = qdrant_store.get_client(cfg)
    qdrant_store.ensure_collection(client, coll, dim)
    qdrant_store.upsert_claims(client, coll, claims, vectors)
    return len(claims)


def main() -> None:
    cfg = get_config()
    coll = cfg.qdrant["claim_collection"]
    dim = int(cfg.models["embedding"]["dimension"])

    claims = list(claim_store.load_claims().values())
    print(f"Embedding {len(claims)} claims with {cfg.models['embedding']['model']}...")
    texts = [f"{c.claim_text} {c.quote_span}".strip() for c in claims]
    vectors = embedder.embed(texts)

    client = qdrant_store.get_client(cfg)
    qdrant_store.ensure_collection(client, coll, dim)
    n = qdrant_store.upsert_claims(client, coll, claims, vectors)
    info = client.get_collection(coll)
    print(f"Upserted {n} claim vectors into '{coll}'. Points now: {info.points_count}")


if __name__ == "__main__":
    main()
