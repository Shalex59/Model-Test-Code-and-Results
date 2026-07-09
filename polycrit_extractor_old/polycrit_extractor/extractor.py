"""Calls the Claude API to extract structured LCCC condition data from a PDF.

Uses:
  * Native PDF document input (text + page-image vision, so scanned/garbled
    pages are still read) -- no separate OCR step.
  * Structured Outputs (output_config.format = json_schema) so the response
    is guaranteed to match schema.build_json_schema(), no manual JSON
    repair/retry logic needed.

Reference: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
           https://platform.claude.com/docs/en/build-with-claude/pdf-support
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import anthropic
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "anthropic SDK is required. Install with: pip install anthropic --break-system-packages"
    ) from exc

from . import pdf_utils
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .schema import build_json_schema

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 16000


@dataclass
class ChunkExtraction:
    label: str
    paper_metadata: dict
    conditions: List[dict] = field(default_factory=list)


def _client(api_key: Optional[str] = None) -> "anthropic.Anthropic":
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "No API key found. Set the ANTHROPIC_API_KEY environment variable "
            "or pass api_key= explicitly."
        )
    return anthropic.Anthropic(api_key=key)


def extract_chunk(
    chunk: pdf_utils.PdfChunk,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    api_key: Optional[str] = None,
    is_multi_chunk: bool = False,
) -> ChunkExtraction:
    """Run extraction on a single PDF (or PDF chunk) and return parsed results."""
    client = _client(api_key)
    chunk_label = chunk.label if is_multi_chunk else ""

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": chunk.data_b64,
                        },
                    },
                    {"type": "text", "text": build_user_prompt(chunk_label)},
                ],
            }
        ],
        output_config={"format": {"type": "json_schema", "schema": build_json_schema()}},
    )

    if response.stop_reason == "refusal":
        raise RuntimeError(
            f"Model declined to process {chunk.label}: response did not complete normally "
            "(stop_reason='refusal'). Inspect the PDF content or try a different chunk size."
        )
    if response.stop_reason == "max_tokens":
        raise RuntimeError(
            f"Response for {chunk.label} was truncated (stop_reason='max_tokens'). "
            "Retry with a higher max_tokens, or a smaller max_pages_per_chunk so each "
            "request covers less material."
        )

    payload = json.loads(response.content[0].text)
    return ChunkExtraction(
        label=chunk.label,
        paper_metadata=payload.get("paper_metadata", {}),
        conditions=payload.get("conditions", []),
    )


def extract_all_chunks(
    pdf_path: str,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    api_key: Optional[str] = None,
    max_pages_per_chunk: int = 25,
    overlap_pages: int = 2,
) -> List[ChunkExtraction]:
    """Split (if needed) and extract every chunk of a PDF."""
    chunks = pdf_utils.split_pdf(
        pdf_path, max_pages_per_chunk=max_pages_per_chunk, overlap_pages=overlap_pages
    )
    multi = len(chunks) > 1
    results = []
    for chunk in chunks:
        results.append(
            extract_chunk(
                chunk,
                model=model,
                max_tokens=max_tokens,
                api_key=api_key,
                is_multi_chunk=multi,
            )
        )
    return results


def merge_paper_metadata(chunk_results: List[ChunkExtraction]) -> dict:
    """Fold multiple chunks' paper_metadata into one record, preferring the
    first non-empty value seen for each field (earlier chunks -- usually the
    first pages, where author/DOI info lives -- take priority)."""
    merged: dict = {}
    for res in chunk_results:
        for k, v in res.paper_metadata.items():
            if v and not merged.get(k):
                merged[k] = v
    return merged
