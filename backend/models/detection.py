from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id"), nullable=True, index=True
    )
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id"), nullable=True, index=True
    )
    detection_type: Mapped[str] = mapped_column(String(100), index=True)
    confidence: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Staff inbox: False = new / unseen alert
    is_seen: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    # Demo / testing sessions — excluded from production queues by default
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    source_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    frame_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
