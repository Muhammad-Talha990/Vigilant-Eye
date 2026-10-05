from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from time_utils import utc_now


class UfmCase(Base):
    __tablename__ = "ufm_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"), index=True)
    reported_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    violation_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Official AU UFM form — recovered / cheating material checklist (JSON array).
    recovered_materials: Mapped[str | None] = mapped_column(Text, nullable=True)
    recovered_other_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id"), nullable=True, index=True
    )
    signer_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    signature_ack: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, onupdate=utc_now
    )
