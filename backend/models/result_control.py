from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ResultControl(Base):
    __tablename__ = "result_controls"
    __table_args__ = (
        UniqueConstraint("case_id", name="uq_result_controls_case_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("ufm_cases.id"), index=True)
    result_status: Mapped[str] = mapped_column(String(50), default="HELD")
    transcript_status: Mapped[str] = mapped_column(String(50), default="BLOCKED")
    reason: Mapped[str] = mapped_column(Text)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    released_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
