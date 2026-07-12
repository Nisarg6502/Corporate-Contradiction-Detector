"""Central config loader for the Corporate Contradiction Detector.

Loads YAML config from this directory, interpolating ``${VAR}`` and
``${VAR:-default}`` references from the environment (populated from a local
``.env`` file if present). Nothing downstream reads YAML directly — everything
goes through :func:`get_config` so that model IDs, topic lists, and DB
connection details stay in one place.

Usage::

    from config import get_config
    cfg = get_config()
    extraction_model = cfg.models["extraction"]["model"]
    topics = cfg.topics
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONFIG_DIR.parent

# ${VAR} or ${VAR:-default}
_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no dependency on python-dotenv).

    Only sets keys that are not already present in os.environ, so real
    environment variables always win over the .env file.
    """
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _interpolate(value: Any) -> Any:
    """Recursively interpolate ${VAR}/${VAR:-default} in strings."""
    if isinstance(value, str):
        def repl(match: re.Match) -> str:
            var, default = match.group(1), match.group(2)
            env_val = os.environ.get(var)
            if env_val is not None:
                return env_val
            if default is not None:
                return default
            raise KeyError(
                f"Required environment variable '{var}' is not set "
                f"(referenced in config). Add it to your .env or environment."
            )
        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


def _load_yaml(name: str) -> dict:
    path = CONFIG_DIR / name
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return _interpolate(data)


@dataclass(frozen=True)
class Config:
    models: dict
    databases: dict
    edgar: dict
    _topics: dict
    processing: dict
    chatbot: dict

    @property
    def topics(self) -> list[dict]:
        """List of topic dicts from topics.yaml."""
        return self._topics.get("topics", [])

    @property
    def topic_ids(self) -> list[str]:
        return [t["id"] for t in self.topics]

    @property
    def neo4j(self) -> dict:
        return self.databases["neo4j"]

    @property
    def qdrant(self) -> dict:
        return self.databases["qdrant"]

    def anthropic_api_key(self) -> str:
        env_name = self.models.get("api_key_env", "ANTHROPIC_API_KEY")
        key = os.environ.get(env_name)
        if not key:
            raise KeyError(
                f"Anthropic API key not found. Set {env_name} in your environment/.env."
            )
        return key


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Load and cache the full project configuration."""
    _load_dotenv(PROJECT_ROOT / ".env")
    return Config(
        models=_load_yaml("models.yaml"),
        databases=_load_yaml("databases.yaml"),
        edgar=_load_yaml("edgar.yaml"),
        _topics=_load_yaml("topics.yaml"),
        processing=_load_yaml("processing.yaml"),
        chatbot=_load_yaml("chatbot.yaml"),
    )
