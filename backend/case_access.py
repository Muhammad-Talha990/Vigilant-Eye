"""Case ownership / access checks and shared staff role sets."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.ufm_case import UfmCase
from models.user import User
from student_portal import resolve_linked_student

# Staff roles that may list portal users (matches GET /users).
STAFF_USER_VIEW_ROLES = frozenset(
    {
        "INVIGILATOR",
        "HOD",
        "DEC",
        "EXAM_DEPARTMENT",
        "UFM_COMMITTEE",
    }
)

# Live monitoring control / status / streams (matches routers.live start/stop).
# C26-FIX: Invigilator only — HOD is case review, not operational surveillance.
MONITOR_ROLES = frozenset({"INVIGILATOR"})

# Detection inbox + mark-seen (aligned with MONITOR_ROLES).
DETECTION_STAFF_ROLES = frozenset({"INVIGILATOR"})

# Case-linked evidence upload (POST /evidence). Viewers use list/file APIs.
EVIDENCE_UPLOAD_ROLES = frozenset({"INVIGILATOR"})

# Institutional reports + case CSV export (NOT monitoring/create sets).
# Invigilator: own reported cases only. Reviewing roles: reporting scope.
REPORTS_ROLES = frozenset(
    {
        "INVIGILATOR",
        "HOD",
        "DEC",
        "EXAM_DEPARTMENT",
        "UFM_COMMITTEE",
    }
)

# Camera registry listing (monitoring + exam setup consumers; not STUDENT).
CAMERA_VIEW_ROLES = frozenset(
    {"INVIGILATOR", "HOD", "DEC", "EXAM_DEPARTMENT"}
)

# Student academic directory API (list/search for case filing + staff pages).
# Invigilator retains GET for Report UFM Incident selectors only — not the
# standalone Students UI module (FE STUDENT_DIRECTORY_VIEW_ROLES excludes Inv).
STUDENT_DIRECTORY_ROLES = STAFF_USER_VIEW_ROLES

# Exam / room catalogs for case filing and master-data pages (not STUDENT).
# Staff retain GET for monitoring & case workflows; Exam Setup UI gate is FE-only
# (roleAccess MASTER_DATA_VIEW_ROLES — currently DEC view).
EXAM_CATALOG_ROLES = frozenset(
    {"INVIGILATOR", "HOD", "DEC", "EXAM_DEPARTMENT"}
)

# --- C22 role-scoped case list / active-queue visibility ---

OPEN_CASE_STATUSES = frozenset(
    {
        "PENDING",
        "UNDER_REVIEW",
        "DEC_REVIEW",
        "EXAM_DEPARTMENT_REVIEW",
        "UFM_COMMITTEE_REVIEW",
    }
)

FINAL_CASE_STATUSES = frozenset({"APPROVED", "REJECTED"})

# Active "awaiting my review" queue — dashboard primary action lists.
ACTIVE_QUEUE_STATUSES_BY_ROLE: dict[str, frozenset[str]] = {
    "HOD": frozenset({"PENDING", "UNDER_REVIEW"}),
    "DEC": frozenset({"DEC_REVIEW"}),
    "EXAM_DEPARTMENT": frozenset({"EXAM_DEPARTMENT_REVIEW"}),
    "UFM_COMMITTEE": frozenset({"UFM_COMMITTEE_REVIEW"}),
}

# Default list / dashboard workspace: cases this role may see without
# premature upstream leakage. HOD is first owner of new PENDING cases.
# DEC/Exam/UFM only see cases that have reached their stage (or later /
# final outcomes they already own for tracking).
CASE_LIST_STATUSES_BY_ROLE: dict[str, frozenset[str]] = {
    "HOD": OPEN_CASE_STATUSES | FINAL_CASE_STATUSES,
    "DEC": frozenset(
        {
            "DEC_REVIEW",
            "EXAM_DEPARTMENT_REVIEW",
            "UFM_COMMITTEE_REVIEW",
        }
    )
    | FINAL_CASE_STATUSES,
    "EXAM_DEPARTMENT": frozenset(
        {
            "EXAM_DEPARTMENT_REVIEW",
            "UFM_COMMITTEE_REVIEW",
        }
    )
    | FINAL_CASE_STATUSES,
    "UFM_COMMITTEE": frozenset({"UFM_COMMITTEE_REVIEW"}) | FINAL_CASE_STATUSES,
}


def active_queue_statuses_for_role(role: str) -> frozenset[str] | None:
    """Statuses for scope=active. None → role has no fixed status set."""
    return ACTIVE_QUEUE_STATUSES_BY_ROLE.get(role)


def case_list_statuses_for_role(role: str) -> frozenset[str] | None:
    """
    Statuses for default / scope=dashboard case lists.

    None means no status restriction from this map (caller applies
    student/invigilator ownership rules separately).
    """
    return CASE_LIST_STATUSES_BY_ROLE.get(role)


def user_can_access_case(db: Session, user: User, case: UfmCase) -> bool:
    """
    Whether the user may view case-linked resources.

    STUDENT: linked student profile owns the case.
    INVIGILATOR: only cases they reported (matches GET /ufm-cases list).
    ADMINISTRATOR: no UFM case access (user-management only).
    Reviewing staff (HOD/DEC/Exam/UFM): institutional case records.
    """
    if user.role == "ADMINISTRATOR":
        return False
    if user.role == "STUDENT":
        linked = resolve_linked_student(db, user)
        return linked is not None and case.student_id == linked.id
    if user.role == "INVIGILATOR":
        return case.reported_by == user.id
    if user.role in {"HOD", "DEC", "EXAM_DEPARTMENT", "UFM_COMMITTEE"}:
        return True
    return False


def assert_can_access_case(db: Session, user: User, case: UfmCase) -> None:
    """Raise 403 if the user cannot access this case."""
    if not user_can_access_case(db, user, case):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own UFM cases",
        )


def assert_can_access_case_id(
    db: Session, user: User, case_id: int | None
) -> UfmCase | None:
    """
    Load case by id and enforce access.

    Returns None when case_id is None (caller decides orphan handling).
    Raises 404 if case_id is set but missing; 403 if unauthorized.
    """
    if case_id is None:
        return None
    case = db.get(UfmCase, case_id)
    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="UFM case not found",
        )
    assert_can_access_case(db, user, case)
    return case
