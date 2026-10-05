"""Phase C23 — Audit Trail User column shows role (display enrichment)."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models.audit_log import AuditLog
from models.base import Base
from models.user import User
from security import create_access_token, hash_password

STAFF_ROLES = [
    "INVIGILATOR",
    "HOD",
    "DEC",
    "EXAM_DEPARTMENT",
    "UFM_COMMITTEE",
    "ADMINISTRATOR",
    "STUDENT",
]


@pytest.fixture()
def client_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    def _get_db():
        db = TestingSession()
        try:
            yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    db = TestingSession()

    def add_user(*, email, role, name=None):
        u = User(
            name=name or email.split("@")[0],
            email=email.lower(),
            password_hash=hash_password("UnusedPass1!"),
            role=role,
            is_active=True,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u

    users = {
        role: add_user(
            email=f"{role.lower()}.c23@demo.com",
            role=role,
            name=f"{role} C23",
        )
        for role in STAFF_ROLES
    }
    # Viewer for /audit-logs (HOD is allowed)
    viewer = users["HOD"]

    for role, user in users.items():
        db.add(
            AuditLog(
                user_id=user.id,
                action="CASE_CREATED",
                entity_type="ufm_case",
                entity_id=user.id,
                description=f"Action by {role}",
                timestamp=datetime(2026, 3, 1, 10, 0, 0),
            )
        )
    # System-style row with no user
    db.add(
        AuditLog(
            user_id=None,
            action="SYSTEM_EVENT",
            entity_type="ufm_case",
            entity_id=None,
            description="No actor",
            timestamp=datetime(2026, 3, 1, 9, 0, 0),
        )
    )
    db.commit()

    def token(user: User) -> str:
        return create_access_token(
            user_id=user.id, email=user.email, role=user.role
        )

    client = TestClient(app)
    yield {
        "client": client,
        "db": db,
        "token": token,
        "viewer": viewer,
        "users": users,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_audit_list_includes_user_role_and_keeps_user_id(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["viewer"]))
    r = c.get("/audit-logs", headers=h)
    assert r.status_code == 200, r.text
    rows = r.json()
    by_user_id = {row["user_id"]: row for row in rows if row["user_id"] is not None}

    for role, user in client_db["users"].items():
        entry = by_user_id[user.id]
        assert entry["user_id"] == user.id
        assert entry["user_role"] == role

    null_actor = next(row for row in rows if row["user_id"] is None)
    assert null_actor["user_role"] is None


def test_audit_user_id_still_stored_unchanged(client_db):
    """Enrichment must not alter persisted audit rows."""
    db = client_db["db"]
    stored = list(db.scalars(select(AuditLog).order_by(AuditLog.id)).all())
    assert any(row.user_id is None for row in stored)
    for row in stored:
        assert not hasattr(row, "user_role") or "user_role" not in row.__table__.c
    assert "user_role" not in AuditLog.__table__.c.keys()
    # user_id values still match creators
    for role, user in client_db["users"].items():
        match = next(r for r in stored if r.description == f"Action by {role}")
        assert match.user_id == user.id
