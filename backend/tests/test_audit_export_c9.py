"""Phase C9 — audit logs CSV export lite (SCOPE-025)."""

from __future__ import annotations

import csv
import io
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models.audit_log import AuditLog
from models.base import Base
from models.user import User
from security import create_access_token, hash_password

EXPECTED_COLUMNS = [
    "id",
    "timestamp",
    "user_id",
    "action",
    "entity_type",
    "entity_id",
    "description",
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

    hod = add_user(email="hod.audit.c9@demo.com", role="HOD", name="Hod Audit")
    inv = add_user(email="inv.audit.c9@demo.com", role="INVIGILATOR", name="Inv Audit")
    student = add_user(
        email="stu.audit.c9@demo.com", role="STUDENT", name="Stu Audit"
    )
    admin = add_user(
        email="admin.audit.c9@demo.com", role="ADMINISTRATOR", name="Admin Audit"
    )

    db.add_all(
        [
            AuditLog(
                user_id=hod.id,
                action="CASE_CREATED",
                entity_type="ufm_case",
                entity_id=11,
                description="Created case UFM-1",
                timestamp=datetime(2026, 1, 1, 10, 0, 0),
            ),
            AuditLog(
                user_id=hod.id,
                action="CASE_REVIEW_FORWARD",
                entity_type="ufm_case",
                entity_id=11,
                description='Forwarded with note: "urgent",\nplease review',
                timestamp=datetime(2026, 1, 2, 10, 0, 0),
            ),
            AuditLog(
                user_id=hod.id,
                action="RESULT_HOLD_CREATED",
                entity_type="result_control",
                entity_id=5,
                description="Hold applied",
                timestamp=datetime(2026, 1, 3, 10, 0, 0),
            ),
        ]
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
        "hod": hod,
        "inv": inv,
        "student": student,
        "admin": admin,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _parse(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def test_audit_export_columns_and_authoritative_values(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["hod"]))
    r = c.get("/audit-logs/export.csv", headers=h)
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers.get("content-type", "")
    assert "audit_logs.csv" in r.headers.get("content-disposition", "")

    reader = csv.reader(io.StringIO(r.text))
    header = next(reader)
    assert header == EXPECTED_COLUMNS

    rows = _parse(r.text)
    assert len(rows) == 3
    # Same order as list endpoint: newest id first
    assert [row["action"] for row in rows] == [
        "RESULT_HOLD_CREATED",
        "CASE_REVIEW_FORWARD",
        "CASE_CREATED",
    ]
    assert rows[2]["entity_id"] == "11"
    assert rows[2]["user_id"] == str(client_db["hod"].id)
    assert "password" not in r.text.lower()
    assert "password_hash" not in r.text.lower()


def test_audit_export_escaping(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["hod"]))
    r = c.get("/audit-logs/export.csv", headers=h)
    rows = _parse(r.text)
    forward = next(row for row in rows if row["action"] == "CASE_REVIEW_FORWARD")
    assert forward["description"] == 'Forwarded with note: "urgent",\nplease review'


def test_audit_export_respects_filters(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["hod"]))

    by_action = c.get(
        "/audit-logs/export.csv",
        headers=h,
        params={"action": "CASE_CREATED"},
    )
    assert by_action.status_code == 200
    rows = _parse(by_action.text)
    assert len(rows) == 1
    assert rows[0]["action"] == "CASE_CREATED"

    by_entity = c.get(
        "/audit-logs/export.csv",
        headers=h,
        params={"entity_type": "result_control"},
    )
    assert len(_parse(by_entity.text)) == 1

    by_q = c.get(
        "/audit-logs/export.csv",
        headers=h,
        params={"q": "urgent"},
    )
    assert len(_parse(by_q.text)) == 1
    assert _parse(by_q.text)[0]["action"] == "CASE_REVIEW_FORWARD"


def test_audit_list_still_works(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["hod"]))
    r = c.get("/audit-logs", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_audit_export_rbac(client_db):
    c = client_db["client"]
    assert (
        c.get(
            "/audit-logs/export.csv",
            headers=_h(client_db["token"](client_db["student"])),
        ).status_code
        == 403
    )
    assert (
        c.get(
            "/audit-logs/export.csv",
            headers=_h(client_db["token"](client_db["inv"])),
        ).status_code
        == 403
    )
    assert (
        c.get(
            "/audit-logs/export.csv",
            headers=_h(client_db["token"](client_db["admin"])),
        ).status_code
        == 403
    )
    assert c.get("/audit-logs/export.csv").status_code in (401, 403)
