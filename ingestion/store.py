"""Intermediate store for parsed documents (JSON on disk).

One JSON file per document under ``data/processed/`` plus an ``index.json``
manifest. JSON (over SQLite) keeps the intermediate output directly inspectable,
which matters for the Checkpoint 1/3 manual sanity checks.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Document

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
INDEX_PATH = PROCESSED_DIR / "index.json"


def _safe_name(document_id: str) -> str:
    return document_id.replace("/", "_").replace(":", "_")


def save_raw_html(document_id: str, html: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{_safe_name(document_id)}.html"
    path.write_text(html, encoding="utf-8")
    return path


def load_raw_html(document_id: str) -> str | None:
    path = RAW_DIR / f"{_safe_name(document_id)}.html"
    return path.read_text(encoding="utf-8") if path.exists() else None


def save_document(doc: Document) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / f"{_safe_name(doc.document_id)}.json"
    path.write_text(json.dumps(doc.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8")
    _update_index(doc)
    return path


def load_document(document_id: str) -> Document:
    path = PROCESSED_DIR / f"{_safe_name(document_id)}.json"
    return Document.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _update_index(doc: Document) -> None:
    index = {}
    if INDEX_PATH.exists():
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    index[doc.document_id] = {
        "document_id": doc.document_id,
        "doc_type": doc.doc_type,
        "date": doc.date,
        "source_type": doc.source_type,
        "company": doc.company,
        "source_url": doc.source_url,
        "n_sections": len(doc.sections),
        "n_chunks": len(doc.chunks),
        "file": f"{_safe_name(doc.document_id)}.json",
    }
    INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False),
                          encoding="utf-8")


def list_documents() -> dict:
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {}
