"""Resolve the student profile linked to a portal user (via students.user_id)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.student import Student
from models.user import User


def resolve_linked_student(db: Session, user: User) -> Student | None:
    """Return the Student record linked to this portal user (STUDENT role only)."""
    if user.role != "STUDENT":
        return None
    return db.scalar(select(Student).where(Student.user_id == user.id))
