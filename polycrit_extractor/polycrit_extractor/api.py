"""Public API. This is the module most callers should use directly."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from . import extractor, validator, excel_writer
from .schema import PAPER_FIELDS


@dataclass
class ExtractionResult:
    paper_metadata: dict
    conditions: List[dict] = field(default_factory=list)
    chunk_labels: List[str] = field(default_factory=list)

    @property
    def n_conditions(self) -> int:
        return len(self.conditions)

    @property
    def n_flagged(self) -> int:
        return sum(1 for r in self.conditions if r.get("flag") not in (None, "", "OK"))


def extract_paper(
    pdf_path: str,
    *,
    model: str = extractor.DEFAULT_MODEL,
    api_key: Optional[str] = None,
    max_pages_per_chunk: int = 25,
    overlap_pages: int = 2,
    max_tokens: int = extractor.DEFAULT_MAX_TOKENS,
    paper_label: Optional[str] = None,
) -> ExtractionResult:
    """Extract every critical / non-critical LCCC condition (plus full
    experimental settings) from a single PDF paper.

    Parameters
    ----------
    pdf_path: path to the PDF.
    model: any current Claude model that supports Structured Outputs and PDF
        input, e.g. "claude-sonnet-5" (default) or "claude-opus-4-8" for
        harder/denser papers.
    api_key: overrides the ANTHROPIC_API_KEY environment variable.
    max_pages_per_chunk / overlap_pages: long papers are split into
        overlapping page-range chunks so each request stays a manageable
        size; the overlap ensures a table/condition that straddles a chunk
        boundary is still fully visible in at least one chunk. Set
        max_pages_per_chunk higher than the paper's page count to force a
        single-shot extraction.
    paper_label: what to put in the "Paper" column. Defaults to the PDF's
        filename.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)

    label = paper_label or os.path.basename(pdf_path)

    chunk_results = extractor.extract_all_chunks(
        pdf_path,
        model=model,
        max_tokens=max_tokens,
        api_key=api_key,
        max_pages_per_chunk=max_pages_per_chunk,
        overlap_pages=overlap_pages,
    )

    paper_metadata = extractor.merge_paper_metadata(chunk_results)
    for k, _ in PAPER_FIELDS:
        paper_metadata.setdefault(k, "")

    all_conditions = []
    for res in chunk_results:
        for cond in res.conditions:
            row = dict(cond)
            row["paper"] = label
            row["source_chunk"] = res.label
            for k, v in paper_metadata.items():
                row.setdefault(k, v)
            all_conditions.append(row)

    all_conditions = validator.flag_duplicates_and_contradictions(all_conditions)

    return ExtractionResult(
        paper_metadata=paper_metadata,
        conditions=all_conditions,
        chunk_labels=[r.label for r in chunk_results],
    )


def extract_to_excel(
    pdf_path: str,
    output_path: str,
    *,
    model: str = extractor.DEFAULT_MODEL,
    api_key: Optional[str] = None,
    max_pages_per_chunk: int = 25,
    overlap_pages: int = 2,
    max_tokens: int = extractor.DEFAULT_MAX_TOKENS,
    paper_label: Optional[str] = None,
    dedupe: bool = False,
) -> ExtractionResult:
    """Convenience wrapper: extract_paper() + write straight to .xlsx.

    Set dedupe=True to hard-drop duplicate rows (identified during
    extraction) instead of just flagging them. Contradictions are never
    auto-resolved -- they are always left in the output, flagged, for a
    human to look at.
    """
    result = extract_paper(
        pdf_path,
        model=model,
        api_key=api_key,
        max_pages_per_chunk=max_pages_per_chunk,
        overlap_pages=overlap_pages,
        max_tokens=max_tokens,
        paper_label=paper_label,
    )

    rows = result.conditions
    if dedupe:
        rows = validator.deduplicate(rows)

    n_contradictions = sum(1 for r in rows if r.get("flag") == "CONTRADICTION")
    n_duplicates = sum(1 for r in rows if str(r.get("flag", "")).startswith("DUPLICATE"))

    notes = [
        f"Extraction Log -- {result.paper_metadata.get('doi') or os.path.basename(pdf_path)}",
        "",
        f"Source PDF: {pdf_path}",
        f"Model: {model}",
        f"Chunks processed: {len(result.chunk_labels)} ({', '.join(result.chunk_labels)})",
        f"Total condition rows extracted: {result.n_conditions}",
        f"Rows flagged as duplicates: {n_duplicates}",
        f"Rows flagged as contradictions (same condition, disagreeing outcome -- needs manual review): {n_contradictions}",
        f"Hard deduplication applied: {dedupe}",
        "",
        "Column meanings, extraction conventions, and classification logic are",
        "documented in polycrit_extractor/schema.py and prompts.py in the source",
        "package this file was generated with.",
    ]

    excel_writer.write_excel(rows, output_path, methodology_notes=notes)
    return result
