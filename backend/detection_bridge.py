"""
Bridge confirmed AI detections -> portal alerts / UFM case drafts.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.audit_log import AuditLog
from models.detection import Detection
from models.exam import Exam
from models.student import Student
from models.ufm_case import UfmCase
from models.user import User
from evidence_auto import attach_detection_evidence_to_case
from notify_helpers import create_notification, notify_student_for_case, notify_users_with_role
from time_utils import utc_now

# Classes that may auto-draft when --auto-draft is used (confirmed only).
UFM_AUTO_DRAFT_CLASSES = {
    "mobile_phone",
    "smart_watch",
    "notes_paper",
    "electronic_gadget",
    "suspicious_object",
    "cell phone",
    "cellphone",
    "phone",
}

VIOLATION_TYPE_MAP = {
    "mobile_phone": "MOBILE_PHONE",
    "smart_watch": "SMART_WATCH",
    "notes_paper": "NOTES_PAPER",
    "electronic_gadget": "ELECTRONIC_GADGET",
    "suspicious_object": "SUSPICIOUS_OBJECT",
    "cell phone": "MOBILE_PHONE",
    "cellphone": "MOBILE_PHONE",
    "phone": "MOBILE_PHONE",
    "laptop": "ELECTRONIC_GADGET",
}


def _next_case_number(db: Session) -> str:
    today = utc_now().strftime("%Y%m%d")
    total = db.scalar(select(func.count()).select_from(UfmCase)) or 0
    return f"UFM-{today}-{total + 1:04d}"


def notify_detection_alert(
    db: Session, detection: Detection, *, is_demo: bool = False
) -> int:
    """Notify active Invigilators about a confirmed AI event. Returns count.

    Live AI monitoring / detection alerts are Invigilator-only (C26).
    HOD / DEC / Exam / UFM receive case-workflow notifications, not live AI alerts.
    """
    from case_access import MONITOR_ROLES

    roles = tuple(sorted(MONITOR_ROLES)) or ("INVIGILATOR",)
    users = db.scalars(
        select(User).where(User.role.in_(roles), User.is_active.is_(True))
    ).all()

    model_bit = ""
    mv = getattr(detection, "model_version", None)
    if mv:
        model_bit = f" model={mv}"

    if is_demo or getattr(detection, "is_demo", False):
        title = "[DEMO] AI detection alert"
        message = (
            f"[TEST DATA] Confirmed '{detection.detection_type}' "
            f"(detection confidence={detection.confidence:.2f})"
            f"{model_bit} "
            f"detection_id={detection.id} — not a production exam incident."
        )
        ntype = "DETECTION_ALERT_DEMO"
    else:
        title = "AI detection alert"
        message = (
            f"Confirmed AI event '{detection.detection_type}' "
            f"(detection confidence={detection.confidence:.2f})"
            f"{model_bit} "
            f"detection_id={detection.id}"
        )
        ntype = "DETECTION_ALERT"

    for user in users:
        create_notification(
            db,
            user_id=user.id,
            case_id=None,
            type=ntype,
            title=title,
            message=message,
        )
    return len(users)


def create_draft_case_from_detection(
    db: Session,
    *,
    detection: Detection,
    student_id: int,
    exam_id: int,
    reported_by: int,
) -> UfmCase:
    """Create a PENDING UFM case draft linked to a confirmed detection."""
    if not detection.is_confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only confirmed detections can create a case draft",
        )
    if db.get(Student, student_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student not found for student_id",
        )
    if db.get(Exam, exam_id) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam not found for exam_id",
        )
    from case_camera import resolve_camera_for_case_create
    from exam_ops import assert_student_enrolled_if_roster

    assert_student_enrolled_if_roster(db, exam_id=exam_id, student_id=student_id)

    if db.get(User, reported_by) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found for reported_by",
        )

    resolved_camera_id = resolve_camera_for_case_create(
        db,
        exam_id=exam_id,
        camera_id=None,
        detection=detection,
    )

    violation = VIOLATION_TYPE_MAP.get(
        detection.detection_type.lower(),
        detection.detection_type.upper().replace(" ", "_"),
    )
    created_at = utc_now()
    case = UfmCase(
        case_number=_next_case_number(db),
        student_id=student_id,
        exam_id=exam_id,
        reported_by=reported_by,
        violation_type=violation,
        description=(
            f"[AUTO-DRAFT] Confirmed AI detection #{detection.id}: "
            f"{detection.detection_type} (confidence={detection.confidence:.3f}, "
            f"frame={detection.frame_index}). Review and attach evidence before forwarding."
        ),
        remarks=f"source_detection_id={detection.id}",
        status="PENDING",
        camera_id=resolved_camera_id,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(case)
    db.flush()

    attached = attach_detection_evidence_to_case(
        db, detection_id=detection.id, case_id=case.id
    )

    db.add(
        AuditLog(
            user_id=reported_by,
            action="CASE_DRAFT_FROM_DETECTION",
            entity_type="ufm_case",
            entity_id=case.id,
            description=(
                f"Draft {case.case_number} created from detection #{detection.id} "
                f"({detection.detection_type}); evidence_linked={attached}"
            ),
        )
    )

    notify_users_with_role(
        db,
        role="HOD",
        case_id=case.id,
        type="CASE_DRAFT",
        title="AI-created UFM case draft",
        message=(
            f"{case.case_number} drafted from detection "
            f"'{detection.detection_type}'."
        ),
    )

    student = db.get(Student, student_id)
    notify_student_for_case(
        db,
        student=student,
        case_id=case.id,
        case_number=case.case_number,
        title="UFM case draft created",
        message=(
            f"{case.case_number} was drafted from an AI detection involving "
            f"your student record."
        ),
    )
    return case
