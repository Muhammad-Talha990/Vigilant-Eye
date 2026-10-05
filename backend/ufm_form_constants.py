"""Official Air University UFM form — recovered / cheating material categories.

Source of truth for digital reporting is the AU UFM incident form terminology
listed for VigilantEye (physical PDF was not present in the workspace).
Do not invent additional categories here.
"""

from __future__ import annotations

# Codes persisted in ufm_cases.recovered_materials (JSON array of strings).
RECOVERED_MATERIAL_CODES: tuple[str, ...] = (
    "ANSWER_EXTRA_SHEET",
    "MOBILE_PHONE",
    "CALCULATOR",
    "MATERIAL_ON_BODY",
    "SMART_DEVICES",
    "OTHER",
)

RECOVERED_MATERIAL_LABELS: dict[str, str] = {
    "ANSWER_EXTRA_SHEET": "Answer / extra sheet",
    "MOBILE_PHONE": "Mobile phone",
    "CALCULATOR": "Calculator",
    "MATERIAL_ON_BODY": "Material written on body/body part",
    "SMART_DEVICES": "Smart devices",
    "OTHER": "Other cheating material",
}

# Map official recovered-material selection → existing workflow violation_type.
RECOVERED_TO_VIOLATION: dict[str, str] = {
    "ANSWER_EXTRA_SHEET": "NOTES_PAPER",
    "MOBILE_PHONE": "MOBILE_PHONE",
    "CALCULATOR": "ELECTRONIC_GADGET",
    "MATERIAL_ON_BODY": "SUSPICIOUS_OBJECT",
    "SMART_DEVICES": "SMART_WATCH",
    "OTHER": "OTHER",
}


def primary_violation_from_recovered(codes: list[str] | None) -> str | None:
    """First selected recovered material drives legacy violation_type."""
    if not codes:
        return None
    for code in codes:
        mapped = RECOVERED_TO_VIOLATION.get(code)
        if mapped:
            return mapped
    return None
