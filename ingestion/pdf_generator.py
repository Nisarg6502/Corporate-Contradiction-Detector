"""Render authored transcript YAML into earnings-call PDFs (PyMuPDF).

The layout is deliberately simple and parser-friendly: a title block, a SYNTHETIC
banner, then each turn as a bold "Name, Role" header line followed by the body
paragraph. The header convention is what :mod:`ingestion.pdf_parser` keys on to
segment speaker turns and attribute claims.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPT_DIR = Path(__file__).resolve().parent / "synthetic_transcripts"
RAW_DIR = PROJECT_ROOT / "data" / "raw"

# Page geometry (US Letter, points).
PAGE_W, PAGE_H = 612, 792
MARGIN = 72
CONTENT_W = PAGE_W - 2 * MARGIN
LINE_H = 15
FONT = "helv"
FONT_BOLD = "hebo"


def _load_transcript(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _wrap(text: str, fontname: str, fontsize: float, width: float) -> list[str]:
    """Greedy word wrap using PyMuPDF font metrics."""
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if fitz.get_text_length(trial, fontname=fontname, fontsize=fontsize) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


class _Cursor:
    """Tracks the write position, adding pages as needed."""

    def __init__(self, doc: fitz.Document):
        self.doc = doc
        self.page = doc.new_page(width=PAGE_W, height=PAGE_H)
        self.y = MARGIN

    def _ensure(self, needed: float) -> None:
        if self.y + needed > PAGE_H - MARGIN:
            self.page = self.doc.new_page(width=PAGE_W, height=PAGE_H)
            self.y = MARGIN

    def write_lines(self, lines: list[str], font: str, size: float,
                    color=(0, 0, 0), gap_after: float = 0.0) -> None:
        for ln in lines:
            self._ensure(LINE_H)
            self.page.insert_text((MARGIN, self.y), ln, fontname=font,
                                  fontsize=size, color=color)
            self.y += LINE_H
        self.y += gap_after


def generate_pdf(transcript: dict, out_dir: Path = RAW_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    cur = _Cursor(doc)

    # Title block.
    cur.write_lines(_wrap(transcript["company"]["name"], FONT_BOLD, 15, CONTENT_W),
                    FONT_BOLD, 15)
    cur.write_lines(_wrap(transcript["title"], FONT_BOLD, 12, CONTENT_W),
                    FONT_BOLD, 12)
    cur.write_lines([f"{transcript['quarter']}  |  {transcript['date']}"],
                    FONT, 10, gap_after=4)
    cur.write_lines(["SYNTHETIC DOCUMENT - not a real transcript; for demo use only."],
                    FONT, 9, color=(0.7, 0.2, 0.2), gap_after=12)

    # Speaker turns.
    for turn in transcript["turns"]:
        header = f"{turn['speaker']}, {turn['role']}"
        cur.write_lines(_wrap(header, FONT_BOLD, 11, CONTENT_W), FONT_BOLD, 11,
                        gap_after=2)
        body_lines = _wrap(" ".join(turn["text"].split()), FONT, 11, CONTENT_W)
        cur.write_lines(body_lines, FONT, 11, gap_after=10)

    out_path = out_dir / f"{transcript['document_id']}.pdf"
    doc.save(str(out_path))
    doc.close()
    return out_path


def generate_all(out_dir: Path = RAW_DIR) -> list[Path]:
    paths = []
    for yml in sorted(TRANSCRIPT_DIR.glob("*.yaml")):
        paths.append(generate_pdf(_load_transcript(yml), out_dir))
    return paths


if __name__ == "__main__":
    for p in generate_all():
        print("generated", p)
