"""Checkpoint 0 sanity checks for the config layer.

These verify the config loads cleanly in a fresh environment (no .env required)
and that the plan's hard rules hold: model IDs, topic list, and DB connection
details are all present and config-driven.
"""

import sys
from pathlib import Path

# Make the project root importable when pytest is run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_config  # noqa: E402


def test_config_loads_without_env():
    cfg = get_config()
    assert cfg is not None


def test_models_are_config_driven():
    cfg = get_config()
    # Each pipeline role names a provider + model from the registry — nothing
    # hardcoded in pipeline code.
    for role in ("extraction", "judgment"):
        assert cfg.models[role]["model"], f"{role} model must be set in config"
        provider = cfg.models[role]["provider"]
        assert provider in cfg.models["providers"], f"{role} provider must be registered"


def test_topics_present():
    cfg = get_config()
    topics = cfg.topics
    assert len(topics) >= 9, "expected the full curated v1 topic list"
    for t in topics:
        assert t.get("id") and t.get("name") and t.get("description")
    # IDs must be unique (they are referenced by Claim->Topic edges later).
    ids = cfg.topic_ids
    assert len(ids) == len(set(ids)), "topic ids must be unique"


def test_db_settings_interpolate():
    cfg = get_config()
    # A valid Neo4j URI scheme (bolt:// default, or neo4j+s:// for Aura from .env).
    assert cfg.neo4j["uri"].startswith(("bolt://", "neo4j://", "neo4j+s://"))
    assert str(cfg.qdrant["port"]) == "6333"
    assert "password" in cfg.neo4j
