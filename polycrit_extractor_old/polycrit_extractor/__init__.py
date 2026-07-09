"""
polycrit_extractor
===================

Generalized extraction of critical-condition (LCCC) and non-critical
(SEC / LAC) chromatography data, plus the experimental settings that
produced them, from any polymer-chemistry PDF paper.

This is not paper-specific: it does not assume PEG, PLA, or any particular
polymer class, column chemistry, or solvent system. It works from the same
schema and conventions used across the PolyCrit project's manually-built
negative-condition and critical-condition databases.

Quick start
-----------
    from polycrit_extractor import extract_to_excel

    extract_to_excel("some_paper.pdf", "some_paper_extracted.xlsx")

Requires the ANTHROPIC_API_KEY environment variable to be set, or pass
api_key= explicitly to any of the public functions.
"""

from .api import extract_paper, extract_to_excel, ExtractionResult

__all__ = ["extract_paper", "extract_to_excel", "ExtractionResult"]
__version__ = "0.1.0"
