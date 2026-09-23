"""Portal notification helpers with optional SMTP / EMAIL_MOCK."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from email_notify import send_email
from models.notification import Notification
from models.user import User


def create_notification(
    db: Session,
    *,
    user_id: int,
    case_id: int | None,
    type: str,
    title: str,
    message: str,
    send_mail: bool = True,
) -> None:
    """Create one portal notification; optionally email (MOCK if no SMTP)."""
    db.add(
        Notification(
            user_id=user_id,
            case_id=case_id,
            type=type,
            title=title,
            message=message,
            is_read=False,
        )
    )
    if not send_mail:
        return
    user = db.get(User, user_id)
    if user and user.email:
        send_email(to_email=user.email, subject=title, body=message)


def notify_users_with_role(
    db: Session,
    *,
    role: str,
    case_id: int,
    type: str,
    title: str,
    message: str,
    send_mail: bool = True,
) -> None:
    users = db.scalars(
        select(User).where(User.role == role, User.is_active.is_(True))
    ).all()
    for user in users:
        create_notification(
            db,
            user_id=user.id,
            case_id=case_id,
            type=type,
            title=title,
            message=message,
            send_mail=send_mail,
        )


def notify_student_for_case(
    db: Session,
    *,
    student,
    case_id: int,
    case_number: str,
    title: str = "UFM case filed",
    message: str | None = None,
) -> None:
    """Notify linked student portal user when a case is created/updated."""
    if student is None or not getattr(student, "user_id", None):
        return
    create_notification(
        db,
        user_id=student.user_id,
        case_id=case_id,
        type="CASE_CREATED",
        title=title,
        message=message
        or f"{case_number} was filed involving your student record. You may submit a clarification.",
    )
