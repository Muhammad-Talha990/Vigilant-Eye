from datetime import date, time

from sqlalchemy import Date, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_code: Mapped[str] = mapped_column(String(50), index=True)
    course_name: Mapped[str] = mapped_column(String(150))
    semester: Mapped[str] = mapped_column(String(50))
    exam_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    room_id: Mapped[int] = mapped_column(ForeignKey("exam_rooms.id"), index=True)
