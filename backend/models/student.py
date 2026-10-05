from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    department: Mapped[str] = mapped_column(String(100))
    program: Mapped[str] = mapped_column(String(100))
    # Portal login for this student (nullable until linked / SIS sync)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
        nullable=True,
        index=True,
    )
