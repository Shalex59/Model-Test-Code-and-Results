"""Post-extraction checks: flag repeated results and contradictions.

Mirrors the manual audit steps used throughout the PolyCrit project:
  * duplicate detection via a normalized-tuple hash across the fields that
    define "the same underlying condition"
  * contradiction detection: rows that share the same identity fields but
    disagree on reached_lccc / interaction_parameter_c
"""

from __future__ import annotations

from typing import List

# Fields that define whether two rows describe "the same" underlying
# condition (used for duplicate detection). Deliberately excludes
# free-text explanatory fields (evidence, notes, c_meaning) since those can
# vary in wording between chunks/extraction passes even for the same
# underlying condition.
IDENTITY_FIELDS = [
    "analyte_polymer",
    "mobile_phase_solvents",
    "mobile_phase_ratio",
    "temperature_c",
    "measured_value",
    "value_type",
]

OUTCOME_FIELDS = ["reached_lccc", "interaction_parameter_c"]


def _norm(val: str) -> str:
    return (val or "").strip().lower()


def _identity_key(row: dict) -> tuple:
    return tuple(_norm(row.get(f, "")) for f in IDENTITY_FIELDS)


def flag_duplicates_and_contradictions(rows: List[dict]) -> List[dict]:
    """Adds/overwrites 'flag' and 'flag_detail' on each row in place-ish
    (returns a new list of dicts; does not mutate the input list object,
    but does not deep-copy nested values either)."""
    groups: dict = {}
    for i, row in enumerate(rows):
        key = _identity_key(row)
        # Skip grouping on essentially-empty identities (e.g. missing
        # measured_value) -- too weak a signal to call a duplicate.
        if all(part == "" for part in key):
            continue
        groups.setdefault(key, []).append(i)

    out = [dict(r) for r in rows]
    for key, idxs in groups.items():
        if len(idxs) < 2:
            continue
        outcomes = {tuple(_norm(rows[i].get(f, "")) for f in OUTCOME_FIELDS) for i in idxs}
        if len(outcomes) > 1:
            for i in idxs:
                out[i]["flag"] = "CONTRADICTION"
                out[i]["flag_detail"] = (
                    f"{len(idxs)} rows share the same condition identity "
                    f"{IDENTITY_FIELDS} but disagree on {OUTCOME_FIELDS}. Review manually."
                )
        else:
            for n, i in enumerate(idxs):
                out[i]["flag"] = "DUPLICATE" if n > 0 else "DUPLICATE (kept)"
                out[i]["flag_detail"] = (
                    f"Identical to {len(idxs) - 1} other row(s) on {IDENTITY_FIELDS} "
                    "(likely re-extracted from overlapping chunk pages, or the paper "
                    "itself reports the same condition twice)."
                )

    for row in out:
        if not row.get("flag"):
            row["flag"] = "OK"
        if not row.get("flag_detail"):
            row["flag_detail"] = ""
    return out


def deduplicate(rows: List[dict], keep: str = "first") -> List[dict]:
    """Optional hard dedup: drop all but one row per identity group.
    Run flag_duplicates_and_contradictions first if you want an audit trail
    before this discards anything -- this function does not preserve one."""
    seen = set()
    result = []
    for row in rows:
        key = _identity_key(row)
        if key != tuple("" for _ in IDENTITY_FIELDS) and key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result
