"""Checkpoint 2 orchestrator: authored YAML -> PDF -> parsed Document -> store.

    python -m ingestion.run_synthetic

Generates a PDF per transcript in data/raw/, parses it via the PyMuPDF path, and
writes the parsed Document (source_type=synthetic) into the same data/processed/
store used by the EDGAR path, so downstream checkpoints see one unified corpus.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from ingestion import pdf_generator, pdf_parser, store  # noqa: E402

TRANSCRIPT_DIR = Path(__file__).resolve().parent / "synthetic_transcripts"


def main() -> None:
    ymls = sorted(TRANSCRIPT_DIR.glob("*.yaml"))
    print(f"Found {len(ymls)} authored transcript(s).")
    for yml in ymls:
        meta = yaml.safe_load(yml.read_text(encoding="utf-8"))
        pdf_path = pdf_generator.generate_pdf(meta)
        doc = pdf_parser.parse_pdf(
            pdf_path, document_id=meta["document_id"], doc_type=meta["doc_type"],
            date=str(meta["date"]), company=meta["company"],
            source_url=f"file://{pdf_path.name}",
            period_of_report=meta.get("quarter"),   # e.g. "Q1 FY2026" — fiscal context
        )
        path = store.save_document(doc)
        speakers = sorted({c.speaker for c in doc.chunks if c.speaker})
        print(f"  {doc.document_id}  {doc.date}  turns={len(doc.chunks)}  "
              f"speakers={speakers}  -> {pdf_path.name} + {path.name}")
    print(f"Done. PDFs in {pdf_generator.RAW_DIR}, parsed docs in {store.PROCESSED_DIR}")


if __name__ == "__main__":
    main()
