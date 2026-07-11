"""Neo4j driver wrapper (connection details from config/.env).

Works against Neo4j Desktop (bolt://localhost:7687) or Neo4j Aura Free
(neo4j+s://<id>.databases.neo4j.io) — just point NEO4J_URI/USER/PASSWORD.
"""

from __future__ import annotations

from contextlib import contextmanager

from neo4j import GraphDatabase

from config import get_config


class Neo4j:
    def __init__(self, cfg=None):
        cfg = cfg or get_config()
        nc = cfg.neo4j
        if not nc.get("password"):
            raise RuntimeError(
                "NEO4J_PASSWORD is not set. Start a Neo4j instance (Desktop or "
                "Aura Free) and put its URI/password in .env."
            )
        self._driver = GraphDatabase.driver(nc["uri"], auth=(nc["user"], nc["password"]))
        self._database = nc.get("database", "neo4j")

    def close(self) -> None:
        self._driver.close()

    def verify(self) -> None:
        self._driver.verify_connectivity()

    def run(self, query: str, **params):
        with self._driver.session(database=self._database) as session:
            return list(session.run(query, **params))

    def write(self, query: str, rows: list[dict]):
        with self._driver.session(database=self._database) as session:
            return session.execute_write(lambda tx: list(tx.run(query, rows=rows)))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


@contextmanager
def connect(cfg=None):
    db = Neo4j(cfg)
    try:
        yield db
    finally:
        db.close()
