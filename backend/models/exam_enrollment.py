"""Exam ↔ Student enrollment (Phase 23)."""

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ExamEnrollment(Base):
    __tablename__ = "exam_enrollments"
    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_exam_enrollments_exam_student"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
