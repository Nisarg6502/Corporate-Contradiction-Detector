"""PyMuPDF parsing path for synthetic transcript PDFs.

Parses a generated earnings-call PDF into the same :class:`Document` model as
the EDGAR path, but with ``source_type="synthetic"``, per-turn ``speaker``
attribution, and PDF ``page`` + ``bbox`` position data on every chunk so the
Checkpoint 9 citation viewer can render a page image with a highlight overlay.

Document-level metadata (doc_type/date/company) comes from the authored YAML and
is passed in; text + positions are read authentically from the rendered PDF.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from .models import Chunk, Document, Section

# PyMuPDF is only needed for the synthetic-PDF path (citation viewer /
# ingestion) — imported lazily in each function below so a cold Cloud Run
# container doesn't pay this import cost to serve the plain browsing routes.

_WS_RE = re.compile(r"\s+")
# "Name, Role" header line (bold in the PDF). Name has no comma; role is short.
_SPEAKER_RE = re.compile(r"^(?P<name>[^,]{2,60}),\s+(?P<role>.{2,80})$")
_BOLD_FLAG = 1 << 4  # PyMuPDF span flag bit for bold


_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def _resolve_pdf(pdf_path: str | Path) -> str:
    """Resolve a stored PDF ref to a file that exists here.

    ``raw_ref`` is persisted into the processed-document JSON as whatever
    absolute path existed when the doc was parsed (e.g. a Windows dev path).
    In a container / on another OS that path won't exist, so fall back to
    ``data/raw/<basename>`` where the synthetic PDFs actually ship.
    """
    raw = str(pdf_path)
    if Path(raw).exists():
        return raw
    # The stored ref may be a foreign-OS absolute path (e.g. Windows
    # backslashes). On Linux a PosixPath won't split "C:\a\b.pdf", so its
    # .name is the whole string — normalize separators before taking basename.
    name = Path(raw.replace("\\", "/")).name
    fallback = _RAW_DIR / name
    return str(fallback if fallback.exists() else raw)


def _norm(text: str) -> str:
    return _WS_RE.sub(" ", text.replace("\xa0", " ")).strip()


def _line_text_and_bold(line: dict) -> tuple[str, bool]:
    text = "".join(span["text"] for span in line["spans"])
    bold = any((span.get("flags", 0) & _BOLD_FLAG)
               or "bo" in span.get("font", "").lower()
               for span in line["spans"])
    return _norm(text), bold


def _union(b1, bbox):
    if b1 is None:
        return list(bbox)
    return [min(b1[0], bbox[0]), min(b1[1], bbox[1]),
            max(b1[2], bbox[2]), max(b1[3], bbox[3])]


def parse_pdf(pdf_path: str | Path, *, document_id: str, doc_type: str,
              date: str, company: dict, source_url: str = "",
              period_of_report: str | None = None) -> Document:
    import fitz  # PyMuPDF
    pdf_path = Path(pdf_path)
    pdf = fitz.open(str(pdf_path))

    doc = Document(
        document_id=document_id, doc_type=doc_type, date=date,
        period_of_report=period_of_report, source_url=source_url,
        source_type="synthetic", raw_ref=str(pdf_path), company=company,
        parsed_at=datetime.now(timezone.utc).isoformat(),
    )

    # A "turn" accumulates body lines under the most recent speaker header.
    cur: dict | None = None

    def flush() -> None:
        nonlocal cur
        if cur and cur["text_parts"]:
            ordinal = len(doc.sections)
            section_id = f"s{ordinal:03d}"
            heading = f"{cur['speaker']}, {cur['role']}"
            section = Section(section_id=section_id, ordinal=ordinal, heading=heading)
            text = _norm(" ".join(cur["text_parts"]))
            section.chunks.append(Chunk(
                chunk_id=f"{document_id}#{section_id}#p0",
                document_id=document_id, section_id=section_id,
                paragraph_index=0, text=text, chunk_type="paragraph",
                is_heading=False, char_len=len(text),
                speaker=cur["speaker"], speaker_role=cur["role"],
                page=cur["page"], bbox=cur["bbox"],
            ))
            doc.sections.append(section)
        cur = None

    for page_index, page in enumerate(pdf, start=1):
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:  # skip images
                continue
            for line in block["lines"]:
                text, bold = _line_text_and_bold(line)
                if not text:
                    continue
                m = _SPEAKER_RE.match(text)
                if bold and m and not text.endswith("."):
                    flush()
                    cur = {"speaker": m.group("name").strip(),
                           "role": m.group("role").strip(),
                           "text_parts": [], "page": None, "bbox": None}
                elif cur is not None:
                    cur["text_parts"].append(text)
                    if cur["page"] is None:
                        cur["page"] = page_index
                    cur["bbox"] = _union(cur["bbox"], line["bbox"])
                # else: title/banner/date before first speaker -> ignore
    flush()
    pdf.close()
    return doc


def render_page_png(pdf_path: str | Path, page_number: int, *, dpi: int = 150,
                    save_path: str | Path | None = None) -> bytes:
    """Render a 1-based page to PNG bytes (and optionally save to disk)."""
    import fitz  # PyMuPDF
    pdf = fitz.open(_resolve_pdf(pdf_path))
    pix = pdf[page_number - 1].get_pixmap(dpi=dpi)
    data = pix.tobytes("png")
    pdf.close()
    if save_path:
        Path(save_path).write_bytes(data)
    return data


def find_highlight_rects(pdf_path: str | Path, page_number: int,
                         quote: str) -> list[list[float]]:
    """Return [x0,y0,x1,y1] rects for a quote span on a 1-based page.

    Text spanning a line break yields one rect per line. Used by the citation
    viewer to overlay highlights.
    """
    import fitz  # PyMuPDF
    pdf = fitz.open(_resolve_pdf(pdf_path))
    rects = pdf[page_number - 1].search_for(_norm(quote))
    pdf.close()
    return [[r.x0, r.y0, r.x1, r.y1] for r in rects]
