"""Serialize portal notifications with linked case context."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models.notification import Notification
from models.ufm_case import UfmCase


def enrich_notification(db: Session, note: Notification) -> dict:
    case = db.get(UfmCase, note.case_id) if note.case_id else None
    return {
        "id": note.id,
        "user_id": note.user_id,
        "case_id": note.case_id,
        "type": note.type,
        "title": note.title,
        "message": note.message,
        "is_read": note.is_read,
        "created_at": note.created_at,
        "case_number": case.case_number if case else None,
        "case_status": case.status if case else None,
        "case_violation": case.violation_type if case else None,
    }
