"""Phase 23 — Exam enrollment / invigilator helpers."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.exam_enrollment import ExamEnrollment
from models.exam_invigilator import ExamInvigilator
from models.student import Student
from models.user import User


def assert_student_enrolled_if_roster(
    db: Session, *, exam_id: int, student_id: int
) -> None:
    """If an exam has a roster, the student must be on it. Empty roster = open."""
    roster_count = int(
        db.scalar(
            select(func.count())
            .select_from(ExamEnrollment)
            .where(ExamEnrollment.exam_id == exam_id)
        )
        or 0
    )
    if roster_count == 0:
        return
    linked = db.scalar(
        select(ExamEnrollment).where(
            ExamEnrollment.exam_id == exam_id,
            ExamEnrollment.student_id == student_id,
        )
    )
    if linked is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student is not enrolled in this exam",
        )


def enrollment_out(db: Session, row: ExamEnrollment) -> dict:
    st = db.get(Student, row.student_id)
    return {
        "id": row.id,
        "exam_id": row.exam_id,
        "student_id": row.student_id,
        "student_roll": st.student_id if st else None,
        "student_name": st.name if st else None,
    }


def invigilator_out(db: Session, row: ExamInvigilator) -> dict:
    user = db.get(User, row.user_id)
    return {
        "id": row.id,
        "exam_id": row.exam_id,
        "user_id": row.user_id,
        "user_email": user.email if user else None,
        "user_name": user.name if user else None,
    }
