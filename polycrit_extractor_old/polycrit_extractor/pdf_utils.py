"""PDF loading / splitting helpers.

Claude reads PDFs natively (text layer + page images, so scanned/low-quality
pages are still handled via vision) -- see
https://platform.claude.com/docs/en/build-with-claude/pdf-support
So this module does NOT do any text extraction or OCR itself. Its only job
is to base64-encode the PDF, and -- for long papers -- split it into
page-range chunks so each request stays comfortably within size/page limits
and Claude's attention isn't spread across an entire large PDF at once.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import List

try:
    from pypdf import PdfReader, PdfWriter
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "pypdf is required. Install with: pip install pypdf --break-system-packages"
    ) from exc


@dataclass
class PdfChunk:
    label: str          # e.g. "pages 1-20"
    start_page: int      # 0-indexed, inclusive
    end_page: int         # 0-indexed, inclusive
    data_b64: str


def _encode_bytes(data: bytes) -> str:
    return base64.standard_b64encode(data).decode("utf-8")


def load_whole_pdf(path: str) -> PdfChunk:
    with open(path, "rb") as f:
        raw = f.read()
    reader = PdfReader(io.BytesIO(raw))
    n_pages = len(reader.pages)
    return PdfChunk(
        label=f"pages 1-{n_pages}",
        start_page=0,
        end_page=n_pages - 1,
        data_b64=_encode_bytes(raw),
    )


def split_pdf(path: str, max_pages_per_chunk: int = 25, overlap_pages: int = 2) -> List[PdfChunk]:
    """Split a PDF into overlapping page-range chunks.

    Overlap exists so a condition/table straddling a chunk boundary is fully
    visible in at least one chunk. The validator's deduplication step is
    what cleans up the resulting duplicate rows from the overlap region.
    """
    with open(path, "rb") as f:
        raw = f.read()
    reader = PdfReader(io.BytesIO(raw))
    n_pages = len(reader.pages)

    if n_pages <= max_pages_per_chunk:
        return [load_whole_pdf(path)]

    chunks: List[PdfChunk] = []
    start = 0
    step = max(1, max_pages_per_chunk - overlap_pages)
    while start < n_pages:
        end = min(start + max_pages_per_chunk - 1, n_pages - 1)
        writer = PdfWriter()
        for p in range(start, end + 1):
            writer.add_page(reader.pages[p])
        buf = io.BytesIO()
        writer.write(buf)
        chunks.append(
            PdfChunk(
                label=f"pages {start + 1}-{end + 1}",
                start_page=start,
                end_page=end,
                data_b64=_encode_bytes(buf.getvalue()),
            )
        )
        if end == n_pages - 1:
            break
        start += step
    return chunks


def get_page_count(path: str) -> int:
    with open(path, "rb") as f:
        return len(PdfReader(f).pages)
