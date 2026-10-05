"""
Phase 19 — Administrator workspace separation & admin directory APIs.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
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

    admin = add_user(email="admin19@example.com", role="ADMINISTRATOR")
    student = add_user(email="stu19@example.com", role="STUDENT")
    inv = add_user(email="inv19@example.com", role="INVIGILATOR")
    hod = add_user(email="hod19@example.com", role="HOD")
    dec = add_user(email="dec19@example.com", role="DEC")
    exam = add_user(email="exam19@example.com", role="EXAM_DEPARTMENT")
    ufm = add_user(email="ufm19@example.com", role="UFM_COMMITTEE")
    db.add(
        Student(
            student_id="R19",
            name="Stu19",
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
        "token": token,
        "admin": admin,
        "student": student,
        "inv": inv,
        "hod": hod,
        "dec": dec,
        "exam": exam,
        "ufm": ufm,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_admin_workspace_apis(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    assert c.get("/admin/users/stats", headers=h).status_code == 200
    assert c.get("/admin/users", headers=h).status_code == 200
    assert c.get("/admin/roles", headers=h).status_code == 200
    assert c.get("/admin/system-info", headers=h).status_code == 200
    roles = c.get("/admin/roles", headers=h).json()
    assert any(r["role"] == "ADMINISTRATOR" for r in roles)
    sysinfo = c.get("/admin/system-info", headers=h).json()
    assert "auth_mode" in sysinfo
    assert "JWT_SECRET" not in str(sysinfo)
    assert "password" not in str(sysinfo).lower() or "password_login_enabled" in sysinfo

    stu = c.get("/admin/students", headers=h)
    assert stu.status_code == 200
    assert stu.json()["total"] >= 1

    audit = c.get("/admin/audit-logs", headers=h)
    assert audit.status_code == 200

    created = c.post(
        "/admin/users",
        headers=h,
        json={"email": "phase19.inv@gmail.com", "role": "INVIGILATOR", "name": "P19"},
    )
    assert created.status_code == 201
    uid = created.json()["id"]
    assert (
        c.patch(f"/admin/users/{uid}", headers=h, json={"role": "HOD"}).status_code
        == 200
    )
    assert c.post(f"/admin/users/{uid}/deactivate", headers=h).status_code == 200
    assert c.post(f"/admin/users/{uid}/activate", headers=h).status_code == 200


@pytest.mark.parametrize("role_key", ["student", "inv", "hod", "dec", "exam", "ufm"])
def test_non_admin_denied_phase19_admin_apis(client_db, role_key):
    c = client_db["client"]
    h = _h(client_db["token"](client_db[role_key]))
    for path in (
        "/admin/roles",
        "/admin/system-info",
        "/admin/students",
        "/admin/audit-logs",
        "/admin/users/stats",
    ):
        assert c.get(path, headers=h).status_code == 403


def test_admin_blocked_from_operational_apis(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    assert c.get("/detections", headers=h).status_code == 403
    assert c.get("/cameras", headers=h).status_code == 403
    assert c.get("/live/status", headers=h).status_code == 403
    assert c.get("/students", headers=h).status_code == 403
    cases = c.get("/ufm-cases", headers=h)
    assert cases.status_code == 200
    assert cases.json() == []


def test_forged_jwt_still_denied_phase19(client_db):
    c = client_db["client"]
    inv = client_db["inv"]
    forged = create_access_token(
        user_id=inv.id, email=inv.email, role="ADMINISTRATOR"
    )
    assert c.get("/admin/roles", headers=_h(forged)).status_code == 403


def test_frontend_admin_nav_config_no_operational_links():
    """Static check against host frontend tree when available (Compose API image may omit it)."""
    from pathlib import Path

    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "frontend" / "src" / "config" / "navByRole.js",
        here.parents[3] / "Vigilant Eye" / "frontend" / "src" / "config" / "navByRole.js",
    ]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        pytest.skip("frontend navByRole.js not mounted in this test environment")
    text = path.read_text(encoding="utf-8")
    start = text.index("ADMINISTRATOR: [")
    end = text.index("INVIGILATOR: [", start)
    block = text[start:end]
    for forbidden in (
        "/app/monitoring",
        "/app/detections",
        "/app/cases",
        "/app/evidence",
        "/app/master-data",
        "/app/reports",
    ):
        assert forbidden not in block
    assert "/app/admin/dashboard" in block
    assert "/app/admin/users" in block
