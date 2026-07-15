# polycrit_extractor

Generalized extraction of critical (LCCC, c=0) and non-critical (LAC c>0 / SEC c<0) chromatography conditions -- plus the full experimental settings behind each one -- from any polymer-chemistry PDF paper. Not tied to PEG, PLA, or any specific polymer/column/solvent system.

It's the automated version of the manual paper-reading workflow used throughout the PolyCrit project: read the paper, pull every distinct condition, classify it, cross-check for repeats/contradictions, and land it in an Excel file with the established column schema.

## What counts as "a condition"

A critical or non-critical condition is a property of a (polymer backbone, mobile-phase recipe) pair, not of an individual sample or architecture. If a paper establishes a critical composition with a linear polymer reference, then holds that mobile phase fixed while testing a dozen star-shaped/end-functionalized/branched variants of the same backbone, that is one condition, not a dozen.

The architecture study is real data, but it lives in that one row's `architecture_note`/`notes` fields as context, not as separate rows -- and it does not change that row's `Reached LCCC`/`Interaction Parameter (c)`. A second row for the same backbone only appears when the paper reports a genuinely different recipe (different solvent ratio, solvent system, or temperature) for it, as a single specific numeric value.

This is enforced in the schema (see the `polymer_backbone` field and its description in `schema.py`) and in the extraction prompt (`prompts.py`), and both files include a worked example if you want to see the exact wording sent to the model.

## How it works

1. PDF input is native. The PDF is sent directly to Claude as a `document` content block. Claude reads both the text layer and the page images, so scanned pages, broken text layers, and dense tables/figures are all handled without a separate OCR step.
2. Extraction is schema-constrained. The request uses Structured Outputs (`output_config.format`), so the response is required to match `schema.py`'s JSON Schema.
3. Long papers are chunked. PDFs longer than `max_pages_per_chunk` (default 25) are split into overlapping page-range chunks so each request stays a manageable size. The overlap helps preserve tables or conditions that cross chunk boundaries.
4. Repeats and contradictions are flagged, not silently resolved. Rows that describe the same underlying condition get flagged as `DUPLICATE`. Rows that share that identity but disagree on LCCC outcome get flagged as `CONTRADICTION` and remain in the output for manual review.

## Install

This package requires Python 3.9 or newer. A Conda environment is recommended.

```bash
conda create -n poly_claude python=3.11
conda activate poly_claude

cd polycrit_extractor
python -m pip install --upgrade pip
python -m pip install -e .
```

Verify the installation:

```bash
python -m polycrit_extractor --help
```

## Anthropic API access

The extractor uses Anthropic's Claude API. API access is separate from a Claude chat subscription.

### For PolyCrit group members

The faculty account owner will invite approved students to the PolyCrit Anthropic organization or provide a separately generated project API key. Each student should use an individual API key whenever possible. Do not share one student's key with another person.

After receiving or creating the key, set it in the Terminal session:

```bash
export ANTHROPIC_API_KEY='paste-your-key-here'
```

There must be no spaces around the `=` sign. Keep the quotation marks, but replace the example text with the complete key.

Confirm that Python can see the key without displaying it:

```bash
python -c "import os; print('API key found' if os.getenv('ANTHROPIC_API_KEY') else 'API key missing')"
```

Expected output:

```text
API key found
```

The exported key is available only in that Terminal window. If the Terminal window is closed, run the `export` command again in the new session.

### API-key security

Treat an API key like a password.

Never:

- put the key directly into Python source code;
- paste it into a GitHub issue, pull request, README, email, or chat;
- commit it to the repository;
- include it in screenshots or terminal output;
- share it with another student.

Before committing changes, check that no key was accidentally written to a file:

```bash
grep -RIn "sk-ant-" .
```

This command should return no matches.

If a key is accidentally exposed, revoke it immediately in the Anthropic Console and create a new key.

## Test the API connection

A quick API connection test is provided in `test_api.py`. Run it with:
python test_api.py

test_api.py is already in the directory.
But below is the tempory script called test_api.py
```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=20,
    messages=[
        {
            "role": "user",
            "content": "Reply with exactly: API works",
        }
    ],
)

print(response.content[0].text)
```

Save it as `test_api.py`, then run:

```bash
python test_api.py
```

Expected output:

```text
API works
```

A `401` error usually indicates an authentication problem. A `404 model not found` error means the model identifier needs to be updated to one available to the organization.

## Use as a library

```python
from polycrit_extractor import extract_to_excel

result = extract_to_excel(
    "some_paper.pdf",
    "some_paper_extracted.xlsx",
    model="claude-sonnet-4-6",
)

print(f"{result.n_conditions} rows, {result.n_flagged} flagged for review")
```

Or get the raw structured data without writing Excel:

```python
from polycrit_extractor import extract_paper

result = extract_paper("some_paper.pdf")

for row in result.conditions:
    print(
        row["sample_id"],
        row["reached_lccc"],
        row["interaction_parameter_c"],
    )
```

## Use from the command line

Activate the environment and set the API key before running:

```bash
conda activate poly_claude
export ANTHROPIC_API_KEY='paste-your-key-here'
```

Run one PDF:

```bash
python -m polycrit_extractor \
    input_pdfs/some_paper.pdf \
    -o output_files/some_paper_extracted.xlsx
```

Specify a model and enable deduplication:

```bash
python -m polycrit_extractor \
    input_pdfs/some_paper.pdf \
    -o output_files/some_paper_extracted.xlsx \
    --model claude-sonnet-4-6 \
    --dedupe
```

Use the exact PDF filename. Put quotation marks around paths containing spaces.

## Output schema

Matches the column layout used in the project's existing Excel files (`PLA_qwen_summary.xlsx`, `PLA_Radke2005_data.xlsx`), generalized to drop polymer-class-specific columns in favor of a free-text `Architecture` field that works for any polymer.

Full column lists and descriptions are in `polycrit_extractor/schema.py`. Editing those descriptions changes the information sent to the model and may therefore change extraction behavior.

Key columns include:

| Column | Meaning |
|---|---|
| `Polymer Backbone` | Canonical repeat-unit chemistry; rows sharing this and the recipe fields represent the same condition |
| `Reached LCCC` | `Yes`, `No`, `Borderline/Near-critical`, or `Unclear` |
| `Interaction Parameter (c)` | `0`, `>0`, `<0`, or blank if the paper does not support an assignment |
| `c Meaning` | Plain-language justification specific to the row |
| `Valid?` | `Yes`, or `No` with a reason if the paper flags the value as an artifact or citation from elsewhere |
| `Flag` / `Flag Detail` | Post-processing result: `OK`, `DUPLICATE`, or `CONTRADICTION` |

## Extraction conventions enforced in the prompt

These mirror the conventions used in the project's manual extraction work:

- Every distinct stated value gets its own row; ranges and "various" are skipped rather than averaged or guessed.
- Conditions merely cited from another paper are excluded, or included with `Valid?='No'` and an explanation.
- Companion-block observations are excluded when another block in the same molecule is the actual subject of the critical-point claim.
- Adsorption or exclusion directionality is not inferred without supporting data from the paper.
- Gradient-elution runs are out of scope unless explicitly characterized as a clean isocratic-equivalent LAC or SEC regime.

## Tuning for a specific paper

- For dense or difficult papers, use a stronger model available to the PolyCrit organization.
- For very long papers, lower `max_pages_per_chunk`.
- Increase `overlap_pages` if conditions near chunk boundaries appear to be missing.
- If a response is truncated, raise `max_tokens` or lower `max_pages_per_chunk`.
- Review every `CONTRADICTION` row manually before treating the data as clean.

## What this does not do

- It does not determine whether a paper is in scope for a particular study.
- It does not deduplicate across different papers or files.
- It does not modify or append to an existing Excel file; it writes a new output file for each run.
- It does not replace expert review of extracted conditions.
