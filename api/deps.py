"""Shared, lazily-initialized clients for the API."""

from __future__ import annotations

from functools import lru_cache

from config import get_config


@lru_cache(maxsize=1)
def cfg():
    return get_config()


@lru_cache(maxsize=1)
def neo4j():
    from graph.connection import Neo4j
    return Neo4j(cfg())


@lru_cache(maxsize=1)
def qdrant():
    from vector import qdrant_store
    return qdrant_store.get_client(cfg())


def severities_at_least(min_severity: str) -> list[str]:
    order = ["low", "medium", "high"]
    if min_severity not in order:
        return order
    return order[order.index(min_severity):]


def processed_tickers() -> set:
    return {r["ticker"] for r in neo4j().run("MATCH (co:Company) RETURN co.ticker AS ticker")}


def company_name(ticker: str) -> str | None:
    rows = neo4j().run("MATCH (co:Company {ticker: $ticker}) RETURN co.name AS name", ticker=ticker)
    return rows[0]["name"] if rows else None
