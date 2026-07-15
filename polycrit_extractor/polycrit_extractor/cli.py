"""Command-line interface.

Usage:
    python -m polycrit_extractor paper.pdf -o paper_extracted.xlsx
    python -m polycrit_extractor paper.pdf -o out.xlsx --model claude-sonnet-4-6 --dedupe
"""

from __future__ import annotations

import argparse
import sys

from .api import extract_to_excel
from .extractor import DEFAULT_MODEL


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="polycrit_extractor",
        description="Extract critical/non-critical LCCC conditions + experimental settings from a PDF paper.",
    )
    parser.add_argument("pdf", help="Path to the input PDF paper.")
    parser.add_argument("-o", "--output", required=True, help="Path to write the output .xlsx file.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model to use (default: {DEFAULT_MODEL}).")
    parser.add_argument("--api-key", default=None, help="Overrides ANTHROPIC_API_KEY.")
    parser.add_argument("--max-pages-per-chunk", type=int, default=25)
    parser.add_argument("--overlap-pages", type=int, default=2)
    parser.add_argument("--paper-label", default=None, help="Value for the 'Paper' column (default: filename).")
    parser.add_argument("--dedupe", action="store_true", help="Hard-drop duplicate rows instead of just flagging them.")
    args = parser.parse_args(argv)

    result = extract_to_excel(
        args.pdf,
        args.output,
        model=args.model,
        api_key=args.api_key,
        max_pages_per_chunk=args.max_pages_per_chunk,
        overlap_pages=args.overlap_pages,
        paper_label=args.paper_label,
        dedupe=args.dedupe,
    )

    print(f"Wrote {result.n_conditions} condition rows ({result.n_flagged} flagged) to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
