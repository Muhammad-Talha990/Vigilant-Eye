"""
Bridge confirmed AI detections -> portal alerts / UFM case drafts.
"""

from __future__ import annotations

from datetime import datetime

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
    today = datetime.utcnow().strftime("%Y%m%d")
    total = db.scalar(select(func.count()).select_from(UfmCase)) or 0
    return f"UFM-{today}-{total + 1:04d}"


def notify_detection_alert(
    db: Session, detection: Detection, *, is_demo: bool = False
) -> int:
    """Notify active HOD users about a confirmed detection. Returns count."""
    if is_demo or getattr(detection, "is_demo", False):
        # Demo alerts go only to the same role but marked — do not look like production
        users = db.scalars(
            select(User).where(User.role == "HOD", User.is_active.is_(True))
        ).all()
        title = "[DEMO] AI detection alert"
        message = (
            f"[TEST DATA] Confirmed '{detection.detection_type}' "
            f"(conf={detection.confidence:.2f}) "
            f"detection_id={detection.id} — not a production exam incident."
        )
        for user in users:
            create_notification(
                db,
                user_id=user.id,
                case_id=None,
                type="DETECTION_ALERT_DEMO",
                title=title,
                message=message,
            )
        return len(users)

    users = db.scalars(
        select(User).where(User.role == "HOD", User.is_active.is_(True))
    ).all()
    title = "AI detection alert"
    message = (
        f"Confirmed '{detection.detection_type}' "
        f"(conf={detection.confidence:.2f}) "
        f"detection_id={detection.id}"
    )
    for user in users:
        create_notification(
            db,
            user_id=user.id,
            case_id=None,
            type="DETECTION_ALERT",
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
    if db.get(User, reported_by) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found for reported_by",
        )

    violation = VIOLATION_TYPE_MAP.get(
        detection.detection_type.lower(),
        detection.detection_type.upper().replace(" ", "_"),
    )
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
