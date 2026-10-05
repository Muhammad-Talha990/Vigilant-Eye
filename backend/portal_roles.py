"""Portal role constants for VigilantEye authorization.

Google never assigns these — only DB User.role (and admin tooling) does.
ADMINISTRATOR is intentionally excluded from UFM/monitor/detection staff sets.
"""

from __future__ import annotations

# Full allowlist for portal accounts (including university administrator).
PORTAL_ROLES = frozenset(
    {
        "ADMINISTRATOR",
        "STUDENT",
        "INVIGILATOR",
        "HOD",
        "DEC",
        "EXAM_DEPARTMENT",
        "UFM_COMMITTEE",
    }
)

# Operational UFM / institutional staff (excludes ADMINISTRATOR and STUDENT).
STAFF_PORTAL_ROLES = frozenset(
    {
        "INVIGILATOR",
        "HOD",
        "DEC",
        "EXAM_DEPARTMENT",
        "UFM_COMMITTEE",
    }
)

# Roles that may be assigned via admin create/import (same as PORTAL_ROLES).
ADMIN_ASSIGNABLE_ROLES = PORTAL_ROLES


def normalize_role(role: str | None) -> str:
    return (role or "").strip().upper()


def is_portal_role(role: str | None) -> bool:
    return normalize_role(role) in PORTAL_ROLES


def is_staff_role(role: str | None) -> bool:
    return normalize_role(role) in STAFF_PORTAL_ROLES
