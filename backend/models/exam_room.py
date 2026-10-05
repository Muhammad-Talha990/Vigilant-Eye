from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class ExamRoom(Base):
    __tablename__ = "exam_rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    room_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    building: Mapped[str] = mapped_column(String(100))
    capacity: Mapped[int] = mapped_column(Integer)
