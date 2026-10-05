"""
Phase 21 — Administrator completion & university operations readiness.

Core admin lifecycle was delivered in Phases 18–20. These tests verify
operations-readiness regressions without weakening authorization.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models.audit_log import AuditLog
from models.base import Base
from models.student import Student
from models.user import User
from security import create_access_token, hash_password


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
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    db = TestingSession()

    def add_user(*, email, role, name=None, active=True):
        u = User(
            name=name or email.split("@")[0],
            email=email.lower(),
            password_hash=hash_password("UnusedPass1!"),
            role=role,
            is_active=active,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u

    admin = add_user(email="admin21@example.com", role="ADMINISTRATOR")
    student = add_user(email="stu21@example.com", role="STUDENT")
    inv = add_user(email="inv21@example.com", role="INVIGILATOR")
    hod = add_user(email="hod21@example.com", role="HOD")
    db.add(
        Student(
            student_id="R21",
            name="Stu21",
            department="CS",
            program="BSCS",
            user_id=student.id,
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
        "admin": admin,
        "student": student,
        "inv": inv,
        "hod": hod,
        "add_user": add_user,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_admin_full_lifecycle_without_cli(client_db):
    """UI-equivalent API lifecycle: create → list → role → link → deactivate → reactivate."""
    c = client_db["client"]
    db = client_db["db"]
    h = _h(client_db["token"](client_db["admin"]))

    created = c.post(
        "/admin/users",
        headers=h,
        json={
            "email": "Phase21.Temp@Gmail.com",
            "name": "Phase21 Temp",
            "role": "STUDENT",
            "student_roll": "P21TEMP",
            "is_active": True,
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["email"] == "phase21.temp@gmail.com"
    assert body["student_roll"] == "P21TEMP"
    uid = body["id"]

    listed = c.get("/admin/users", headers=h, params={"q": "phase21.temp"})
    assert listed.status_code == 200
    assert any(u["id"] == uid for u in listed.json()["items"])

    directory = c.get("/admin/students", headers=h, params={"q": "P21TEMP"})
    assert directory.status_code == 200
    items = directory.json()["items"]
    assert items
    assert items[0]["linked_email"] == "phase21.temp@gmail.com"
    assert items[0]["portal_active"] is True

    # Keep STUDENT role; rename only
    patched = c.patch(
        f"/admin/users/{uid}",
        headers=h,
        json={"name": "Phase21 Temp Updated", "student_roll": "P21TEMP"},
    )
    assert patched.status_code == 200
    assert patched.json()["name"] == "Phase21 Temp Updated"

    assert c.post(f"/admin/users/{uid}/deactivate", headers=h).status_code == 200
    assert c.get(f"/admin/users/{uid}", headers=h).json()["is_active"] is False
    assert c.post(f"/admin/users/{uid}/activate", headers=h).status_code == 200
    assert c.get(f"/admin/users/{uid}", headers=h).json()["is_active"] is True

    actions = set(db.scalars(select(AuditLog.action)).all())
    assert "USER_CREATED" in actions
    assert "USER_DEACTIVATED" in actions
    assert "USER_REACTIVATED" in actions


def test_csv_preview_never_overwrites_role(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    csv_text = (
        "email,role,name,student_roll\n"
        "stu21@example.com,HOD,WouldOverwrite,\n"
        "fresh21@gmail.com,INVIGILATOR,Fresh,\n"
    )
    prev = c.post(
        "/admin/users/import/preview",
        headers=h,
        files={"file": ("s.csv", io.BytesIO(csv_text.encode()), "text/csv")},
    )
    assert prev.status_code == 200
    body = prev.json()
    assert len(body["role_conflicts"]) >= 1
    assert body["can_import_count"] >= 1
    conf = c.post("/admin/users/import", headers=h, json={"rows": body["valid"]})
    assert conf.status_code == 200
    assert client_db["student"].role == "STUDENT"


def test_safety_forged_jwt_and_last_admin(client_db):
    c = client_db["client"]
    inv = client_db["inv"]
    forged = create_access_token(
        user_id=inv.id, email=inv.email, role="ADMINISTRATOR"
    )
    assert c.get("/admin/users", headers=_h(forged)).status_code == 403

    admin = client_db["admin"]
    h = _h(client_db["token"](admin))
    assert (
        c.post(f"/admin/users/{admin.id}/deactivate", headers=h).status_code == 400
    )
    assert (
        c.patch(
            f"/admin/users/{admin.id}", headers=h, json={"role": "HOD"}
        ).status_code
        == 400
    )


@pytest.mark.parametrize("role_key", ["student", "inv", "hod"])
def test_non_admin_blocked(client_db, role_key):
    c = client_db["client"]
    h = _h(client_db["token"](client_db[role_key]))
    assert c.get("/admin/users", headers=h).status_code == 403
    assert c.get("/admin/system-info", headers=h).status_code == 403


def test_system_info_has_no_secrets(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    info = c.get("/admin/system-info", headers=h).json()
    blob = str(info).lower()
    assert "jwt_secret" not in blob
    assert "postgres_password" not in blob
    assert "smtp_password" not in blob
    assert info.get("password_login_enabled") is not None
