"""Portal notification helpers with optional SMTP / EMAIL_MOCK.

Portal notifications always persist. Email is queued until after a successful
DB commit so SMTP failures never roll back workflow state.

Authoritative recipient: User.email for Notification.user_id (server-side only).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from email_notify import PORTAL_BASE_URL, send_email
from email_templates import build_notification_email
from models.notification import Notification
from models.user import User

# In-app always; email for important institutional events only.
# CLARIFICATION covers student clarification request/submit flows in main.py.
# CLARIFICATION_SUBMITTED kept for compatibility if used elsewhere.
_EMAIL_NOTIFICATION_TYPES = frozenset(
    {
        "CASE_CREATED",
        "CASE_STATUS",
        "CASE_ACTION_REQUIRED",
        "CLARIFICATION",
        "CLARIFICATION_SUBMITTED",
        "RESULT_RELEASED",
        "RESULT_HOLD",
        "DETECTION_ALERT",
    }
)


def notification_type_sends_email(type: str) -> bool:
    """Whether this notification type is eligible for SMTP (when enabled)."""
    if type in _EMAIL_NOTIFICATION_TYPES:
        return True
    # Broader CASE_* workflow events (e.g. CASE_DRAFT from detection bridge).
    return str(type).startswith("CASE_")


def _queue_email_after_commit(db: Session, payload: dict[str, Any]) -> None:
    """
    Defer SMTP until after_commit so a failed send cannot unwind DB work,
    and a rolled-back transaction never sends mail.
    """
    pending = db.info.setdefault("ve_pending_emails", [])
    pending.append(payload)
    if db.info.get("ve_email_listener_registered"):
        return
    db.info["ve_email_listener_registered"] = True

    @event.listens_for(db, "after_commit", once=True)
    def _on_commit(session: Session) -> None:
        items = list(session.info.pop("ve_pending_emails", []))
        session.info.pop("ve_email_listener_registered", None)
        for item in items:
            try:
                send_email(**item)
            except Exception:  # noqa: BLE001 — belt-and-suspenders; send_email never raises
                pass

    @event.listens_for(db, "after_rollback", once=True)
    def _on_rollback(session: Session) -> None:
        session.info.pop("ve_pending_emails", None)
        session.info.pop("ve_email_listener_registered", None)


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
    """Create one portal notification; optionally email (never fails the caller)."""
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
    if not notification_type_sends_email(type):
        return
    user = db.get(User, user_id)
    if user is None or not user.email:
        return
    # Inactive accounts: portal row may still be recorded; do not email.
    if not bool(getattr(user, "is_active", True)):
        return

    content = build_notification_email(
        title=title,
        message=message,
        case_id=case_id,
        notification_type=type,
        portal_base_url=PORTAL_BASE_URL or None,
    )
    _queue_email_after_commit(
        db,
        {
            "to_email": user.email,
            "subject": content.subject,
            "body": content.text,
            "html": content.html,
        },
    )


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
