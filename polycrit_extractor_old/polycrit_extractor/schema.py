"""
Schema shared by the extractor (Claude structured outputs) and the Excel
writer, so the two never drift apart.

Design notes
------------
* Every field is a required string. Unknown / not-applicable is represented
  as "" rather than null. This keeps the JSON Schema free of optional
  parameters and union ("anyOf") types, which is what actually costs you
  against the Structured Outputs complexity limits (24 optional params /
  16 union-typed params per request) -- see
  https://platform.claude.com/docs/en/build-with-claude/structured-outputs
* Numeric-looking fields (temperature, elution value, publication year...)
  are still typed as strings on purpose. Papers frequently report these as
  "irreversible adsorption", "50 +/- 1", or a footnoted range instead of a
  clean number, and a strict "number" type would force the model to drop
  that information or fail to match the schema. Numeric parsing happens
  downstream in excel_writer.py, on a best-effort basis, without discarding
  the original text.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Paper-level metadata (one per paper)
# ---------------------------------------------------------------------------
PAPER_FIELDS = [
    ("doi", "DOI"),
    ("publication_year", "Publication Year"),
    ("corresponding_author", "Corresponding Author"),
    ("email", "Email"),
    ("physical_address", "Physical Address"),
]

# ---------------------------------------------------------------------------
# Per-condition fields (one row per distinct reported condition / data point)
# ---------------------------------------------------------------------------
CONDITION_FIELDS = [
    ("sample_id", "Sample ID"),
    ("analyte_polymer", "Analyte Polymer"),
    ("critical_component", "Critical Component"),
    ("architecture_note", "Architecture"),
    ("condition_basis", "Critical Condition Basis"),
    ("column_name", "Column Name"),
    ("stationary_phase_chemistry", "Stationary Phase Chemistry"),
    ("column_mode", "Column Mode"),
    ("pore_size", "Pore Size"),
    ("column_dimensions", "Column Dimensions"),
    ("mobile_phase_solvents", "Mobile Phase Solvents"),
    ("mobile_phase_ratio", "Mobile Phase Ratio"),
    ("mobile_phase_ratio_units", "Mobile Phase Ratio Units"),
    ("aqueous_ph", "Aqueous pH"),
    ("aqueous_salt_added", "Aqueous Salt Added"),
    ("aqueous_salt_type", "Aqueous Salt Type"),
    ("aqueous_salt_concentration", "Aqueous Salt Concentration"),
    ("temperature_c", "Temperature (C)"),
    ("flow_rate", "Flow Rate"),
    ("detector", "Detector"),
    ("molar_mass_info", "Molar Mass Info"),
    ("value_type", "Measured Value Type"),
    ("measured_value", "Measured Value"),
    ("reached_lccc", "Reached LCCC"),
    ("interaction_parameter_c", "Interaction Parameter (c)"),
    ("c_meaning", "c Meaning"),
    ("valid", "Valid?"),
    ("evidence", "Evidence"),
    ("notes", "Notes"),
]

# Columns added by this tool's own post-processing (validator.py), not by
# the model.
DERIVED_FIELDS = [
    ("source_chunk", "Source Chunk (pages)"),
    ("flag", "Flag"),
    ("flag_detail", "Flag Detail"),
]

# Full row schema in Excel column order: Paper, DOI... then condition
# fields, then derived fields.
EXCEL_COLUMNS = (
    [("paper", "Paper")]
    + PAPER_FIELDS
    + CONDITION_FIELDS
    + DERIVED_FIELDS
)


def _string_field(description: str) -> dict:
    return {"type": "string", "description": description}


PAPER_FIELD_DESCRIPTIONS = {
    "doi": "Digital Object Identifier, e.g. 10.1016/j.polymer.2005.05.028. Empty string if not stated in the text.",
    "publication_year": "Four-digit publication year as a string.",
    "corresponding_author": "Corresponding author name(s), semicolon-separated if more than one.",
    "email": "Corresponding author email(s), semicolon-separated if more than one.",
    "physical_address": "Corresponding author institutional address(es), semicolon-separated if more than one.",
}

CONDITION_FIELD_DESCRIPTIONS = {
    "sample_id": "The paper's own label for this sample/run if it has one (e.g. 'A1', 'Run 3', 'Table 2 row 4'). If the paper does not label it, invent a short stable ID such as 'p5-para2-cond1'.",
    "analyte_polymer": "The specific polymer/architecture analyzed in this exact condition (not just the polymer class).",
    "critical_component": "The chemical unit or component whose critical adsorption point is being probed (often the repeating-unit backbone).",
    "architecture_note": "Free-text structural description relevant to this condition: linear/star/block/graft, arm count, end groups, degree of branching, etc. Empty string if not architecture-specific.",
    "condition_basis": "One sentence, in your own words, describing why this specific condition is reported as critical or non-critical in the paper (e.g. what evidence the authors used).",
    "column_name": "Stationary phase / column product name as given in the paper.",
    "stationary_phase_chemistry": "e.g. bare silica, C18, amino-bonded, etc.",
    "column_mode": "Normal phase, reversed phase, etc.",
    "pore_size": "Column pore size(s) as reported.",
    "column_dimensions": "Column length x internal diameter, as reported.",
    "mobile_phase_solvents": "The solvent(s) making up the mobile phase for this condition.",
    "mobile_phase_ratio": "The specific numeric ratio/composition used for THIS condition. Do not log a condition if the paper only gives a range or 'various' without a single specific ratio -- skip it instead.",
    "mobile_phase_ratio_units": "Units for the ratio, e.g. v/v, vol%, wt%.",
    "aqueous_ph": "pH of the aqueous mobile-phase component, if applicable. Empty string for non-aqueous systems.",
    "aqueous_salt_added": "'True', 'False', or '' if not applicable/not stated.",
    "aqueous_salt_type": "Salt identity if added.",
    "aqueous_salt_concentration": "Salt concentration if added.",
    "temperature_c": "Column/experiment temperature in Celsius, as text (convert from F/K if the paper uses those, and note the conversion in notes).",
    "flow_rate": "Mobile phase flow rate, with units, as reported.",
    "detector": "Detector(s) used, e.g. RI, UV, ELSD, MALLS.",
    "molar_mass_info": "Molar mass / dispersity information specific to this sample (Mn, Mw, Mw/Mn, and their source e.g. theoretical vs SEC-MALLS), in free text.",
    "value_type": "What kind of measured value 'measured_value' holds, e.g. 'elution volume (ml)', 'retention time (min)', 'retention factor k prime'. Use whatever the paper actually reports.",
    "measured_value": "The measured value itself, as text (e.g. '4.69', 'irreversible adsorption / does not elute'). Never round or convert without saying so in notes.",
    "reached_lccc": "One of: 'Yes', 'No', 'Borderline/Near-critical', 'Unclear'. "
                    "'Yes' only if the paper's own evidence supports a true critical point (e.g. elution independent of molar mass). "
                    "'Borderline/Near-critical' if the data sits at the edge of a critical baseline range the paper itself established, without the paper explicitly resolving it. "
                    "'Unclear' if there truly is not enough information to say either way -- do not guess.",
    "interaction_parameter_c": "'0' for true LCCC, '>0' for adsorption/LAC-dominant, '<0' for exclusion/SEC-dominant, or '' if the paper gives no basis to assign a sign. "
                               "Never invent a numeric c value the paper did not report or that you did not derive from an explicit, stated relationship in the paper.",
    "c_meaning": "Plain-language explanation of the interaction_parameter_c call for this specific row, referencing what in the data supports it.",
    "valid": "'Yes' normally. 'No' plus a short reason if this specific data point is something the paper itself flags as an artifact, a defect, an outlier removed from their own analysis, or a value merely cited from another paper rather than newly generated here.",
    "evidence": "A SHORT (under ~20 words) paraphrase, in your own words, of the paper's basis for this row. Do not copy long verbatim passages.",
    "notes": "Anything else useful: caveats, cross-references to other rows, unit conversions performed, ambiguities.",
}


def build_json_schema() -> dict:
    """Build the JSON Schema passed to output_config.format for Structured Outputs."""
    paper_props = {k: _string_field(PAPER_FIELD_DESCRIPTIONS[k]) for k, _ in PAPER_FIELDS}
    condition_props = {k: _string_field(CONDITION_FIELD_DESCRIPTIONS[k]) for k, _ in CONDITION_FIELDS}

    condition_item_schema = {
        "type": "object",
        "properties": condition_props,
        "required": [k for k, _ in CONDITION_FIELDS],
        "additionalProperties": False,
    }

    return {
        "type": "object",
        "properties": {
            "paper_metadata": {
                "type": "object",
                "properties": paper_props,
                "required": [k for k, _ in PAPER_FIELDS],
                "additionalProperties": False,
            },
            "conditions": {
                "type": "array",
                "description": (
                    "One entry per distinct reported experimental condition or data "
                    "point relevant to establishing or testing a critical adsorption "
                    "point. Include BOTH critical (c=0) and non-critical (c>0 / c<0) "
                    "conditions. Split ranges and multi-value table rows into one "
                    "entry per single stated value -- never collapse several data "
                    "points into one row."
                ),
                "items": condition_item_schema,
            },
        },
        "required": ["paper_metadata", "conditions"],
        "additionalProperties": False,
    }
