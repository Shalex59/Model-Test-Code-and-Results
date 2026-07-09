# polycrit_extractor

Generalized extraction of **critical (LCCC, c=0)** and **non-critical
(LAC c>0 / SEC c<0)** chromatography conditions -- plus the full
experimental settings behind each one -- from any polymer-chemistry PDF
paper. Not tied to PEG, PLA, or any specific polymer/column/solvent system.

It's the automated version of the manual paper-reading workflow used
throughout the PolyCrit project: read the paper, pull every distinct
condition, classify it, cross-check for repeats/contradictions, and land it
in an Excel file with the established column schema.

## How it works

1. **PDF input is native.** The PDF is sent directly to Claude as a
   `document` content block. Claude reads both the text layer and the page
   images, so scanned pages, broken text layers, and dense tables/figures
   are all handled without a separate OCR step.
2. **Extraction is schema-constrained.** The request uses
   [Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
   (`output_config.format`), so the response is *guaranteed* to match
   `schema.py`'s JSON Schema -- no manual JSON-repair/retry logic needed.
3. **Long papers are chunked.** PDFs longer than `max_pages_per_chunk`
   (default 25) are split into overlapping page-range chunks so each
   request stays a manageable size and Claude's attention isn't spread
   across the whole document at once. The overlap means a table/condition
   that straddles a chunk boundary still lands fully in at least one chunk.
4. **Repeats and contradictions are flagged, not silently resolved.** Rows
   that describe the same underlying condition (same polymer, solvents,
   ratio, temperature, measured value) get flagged as `DUPLICATE`. Rows
   that share that same identity but *disagree* on LCCC outcome get flagged
   as `CONTRADICTION` and are always left in the output for manual review
   (never auto-resolved).

## Install

```bash
pip install -r requirements.txt --break-system-packages
export ANTHROPIC_API_KEY=sk-ant-...
```

## Use as a library

```python
from polycrit_extractor import extract_to_excel

result = extract_to_excel(
    "some_paper.pdf",
    "some_paper_extracted.xlsx",
    model="claude-sonnet-5",      # or "claude-opus-4-8" for harder/denser papers
)

print(f"{result.n_conditions} rows, {result.n_flagged} flagged for review")
```

Or get the raw structured data without writing Excel:

```python
from polycrit_extractor import extract_paper

result = extract_paper("some_paper.pdf")
for row in result.conditions:
    print(row["sample_id"], row["reached_lccc"], row["interaction_parameter_c"])
```

## Use from the command line

```bash
python -m polycrit_extractor some_paper.pdf -o some_paper_extracted.xlsx
python -m polycrit_extractor some_paper.pdf -o out.xlsx --model claude-opus-4-8 --dedupe
```

## Output schema

Matches the column layout used in the project's existing Excel files
(`PLA_qwen_summary.xlsx`, `PLA_Radke2005_data.xlsx`), generalized to drop
polymer-class-specific columns (e.g. arm count) in favor of a free-text
`Architecture` field that works for any polymer. Full column list and field
descriptions live in `polycrit_extractor/schema.py`
(`PAPER_FIELDS`, `CONDITION_FIELDS`, and the `*_DESCRIPTIONS` dicts --
those descriptions are also what get sent to the model, so editing them
changes extraction behavior directly).

Key columns:

| Column | Meaning |
|---|---|
| `Reached LCCC` | `Yes` / `No` / `Borderline/Near-critical` / `Unclear` |
| `Interaction Parameter (c)` | `0`, `>0`, `<0`, or blank if the paper gives no basis to assign a sign |
| `c Meaning` | plain-language justification for that call, specific to the row |
| `Valid?` | `Yes`, or `No` + reason if the paper itself flags this data point as an artifact/defect/citation-from-elsewhere |
| `Flag` / `Flag Detail` | added by this tool's own post-processing: `OK`, `DUPLICATE`, or `CONTRADICTION` |

## Extraction conventions enforced in the prompt

These mirror the conventions used in the project's manual extraction work
(see `prompts.py` for the exact wording sent to the model):

- Every distinct stated value gets its own row; ranges and "various" are
  **skipped**, not averaged or guessed.
- Conditions merely *cited* from another paper (not newly generated in this
  one) are excluded, or included with `Valid?='No'` and an explanation.
- "Companion-block" observations (a block deliberately held off-critical
  while a different block in the same molecule is the actual subject of the
  critical-point claim) are excluded.
- No inferred adsorption/exclusion directionality without the paper's own
  data supporting it -- ambiguous points get `Unclear`/blank `c`, not a
  guess.
- Gradient-elution runs are out of scope unless explicitly characterized as
  a clean isocratic-equivalent LAC or SEC regime.

## Tuning for a specific paper

- **Dense/hard-to-parse papers** (heavy equations, many sub-tables): try
  `model="claude-opus-4-8"`.
- **Very long papers**: lower `max_pages_per_chunk` so each request covers
  less material; raise `overlap_pages` if you notice conditions near chunk
  boundaries going missing.
- **If a response gets truncated** (`stop_reason='max_tokens'`), raise
  `max_tokens` or lower `max_pages_per_chunk`.
- Review every `CONTRADICTION`-flagged row by hand before treating the
  database as clean -- this tool deliberately never auto-resolves those.

## What this does *not* do

- It does not decide on its own whether a paper is in scope for your study
  (e.g. the project's "pre-2000 papers aren't relevant" rule) -- that's a
  judgment call to make before or after running this on a given PDF.
- It does not deduplicate *across* papers/files -- only within a single
  extraction run. Cross-paper deduplication against an existing database
  (like the project's negative-dataset workflow does) is a separate step.
- It does not modify or append to any existing Excel file -- it always
  writes a fresh file for the one paper it was run on.
