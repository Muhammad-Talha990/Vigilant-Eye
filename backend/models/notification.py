from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from time_utils import utc_now


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    case_id: Mapped[int | None] = mapped_column(
        ForeignKey("ufm_cases.id"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(150))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
