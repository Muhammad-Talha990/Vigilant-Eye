"""
Phase 18 — ADMINISTRATOR user management, bulk import, last-admin safety.
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

    admin = add_user(email="admin@example.com", role="ADMINISTRATOR", name="Admin")
    student = add_user(email="student@example.com", role="STUDENT", name="Stu")
    inv = add_user(email="inv@example.com", role="INVIGILATOR", name="Inv")
    hod = add_user(email="hod@example.com", role="HOD", name="Hod")
    dec = add_user(email="dec@example.com", role="DEC", name="Dec")
    exam = add_user(email="exam@example.com", role="EXAM_DEPARTMENT", name="Exam")
    ufm = add_user(email="ufm@example.com", role="UFM_COMMITTEE", name="Ufm")

    st = Student(
        student_id="S100",
        name="Stu",
        department="CS",
        program="BSCS",
        user_id=student.id,
    )
    db.add(st)
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
        "dec": dec,
        "exam": exam,
        "ufm": ufm,
        "Session": TestingSession,
        "add_user": add_user,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


@pytest.mark.parametrize(
    "role_key",
    ["student", "inv", "hod", "dec", "exam", "ufm"],
)
def test_non_admin_denied_admin_endpoints(client_db, role_key):
    c = client_db["client"]
    user = client_db[role_key]
    h = _auth(client_db["token"](user))
    assert c.get("/admin/users", headers=h).status_code == 403
    assert c.get("/admin/users/stats", headers=h).status_code == 403
    assert c.post(
        "/admin/users",
        headers=h,
        json={"email": "x@y.com", "role": "INVIGILATOR"},
    ).status_code == 403
    assert c.post(
        "/admin/users/1/activate",
        headers=h,
    ).status_code == 403
    csv_body = b"email,role,name,student_roll\na@b.com,INVIGILATOR,A,\n"
    assert (
        c.post(
            "/admin/users/import/preview",
            headers=h,
            files={"file": ("users.csv", io.BytesIO(csv_body), "text/csv")},
        ).status_code
        == 403
    )


def test_admin_list_search_filter_pagination(client_db):
    c = client_db["client"]
    h = _auth(client_db["token"](client_db["admin"]))
    r = c.get("/admin/users", headers=h, params={"page": 1, "page_size": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["page"] == 1
    assert body["page_size"] == 3
    assert body["total"] >= 7
    assert len(body["items"]) == 3
    assert "password_hash" not in body["items"][0]

    r2 = c.get("/admin/users", headers=h, params={"q": "hod@example.com"})
    assert r2.status_code == 200
    assert r2.json()["total"] == 1
    assert r2.json()["items"][0]["role"] == "HOD"

    r3 = c.get("/admin/users", headers=h, params={"role": "STUDENT", "linked": "linked"})
    assert r3.status_code == 200
    assert r3.json()["total"] >= 1

    stats = c.get("/admin/users/stats", headers=h)
    assert stats.status_code == 200
    assert stats.json()["total"] >= 7
    assert "ADMINISTRATOR" in stats.json()["by_role"]


def test_admin_create_activate_deactivate_role_link(client_db):
    c = client_db["client"]
    db = client_db["db"]
    h = _auth(client_db["token"](client_db["admin"]))

    created = c.post(
        "/admin/users",
        headers=h,
        json={
            "email": "new.inv@gmail.com",
            "role": "INVIGILATOR",
            "name": "New Inv",
        },
    )
    assert created.status_code == 201
    uid = created.json()["id"]
    assert created.json()["role"] == "INVIGILATOR"
    assert created.json()["is_active"] is True

    stu = c.post(
        "/admin/users",
        headers=h,
        json={
            "email": "roll200@students.au.edu.pk",
            "role": "STUDENT",
            "name": "Roll200",
            "student_roll": "200",
        },
    )
    assert stu.status_code == 201
    assert stu.json()["student_roll"] == "200"

    patched = c.patch(
        f"/admin/users/{uid}",
        headers=h,
        json={"role": "HOD", "name": "Promoted"},
    )
    assert patched.status_code == 200
    assert patched.json()["role"] == "HOD"

    deact = c.post(f"/admin/users/{uid}/deactivate", headers=h)
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    # Inactive user cannot use API
    bad = c.get("/auth/me", headers=_auth(client_db["token"](db.get(User, uid))))
    # token was minted with old user object — reload
    db.expire_all()
    u = db.get(User, uid)
    tok = create_access_token(user_id=u.id, email=u.email, role=u.role)
    assert c.get("/auth/me", headers=_auth(tok)).status_code == 401

    act = c.post(f"/admin/users/{uid}/activate", headers=h)
    assert act.status_code == 200
    assert act.json()["is_active"] is True

    audits = db.scalars(
        select(AuditLog).where(AuditLog.entity_type == "user")
    ).all()
    actions = {a.action for a in audits}
    assert "USER_CREATED" in actions
    assert "USER_ROLE_CHANGED" in actions
    assert "USER_DEACTIVATED" in actions
    assert "USER_REACTIVATED" in actions


def test_last_admin_protection(client_db):
    c = client_db["client"]
    admin = client_db["admin"]
    h = _auth(client_db["token"](admin))
    r = c.post(f"/admin/users/{admin.id}/deactivate", headers=h)
    assert r.status_code == 400
    assert "last active ADMINISTRATOR" in r.json()["detail"]

    r2 = c.patch(
        f"/admin/users/{admin.id}",
        headers=h,
        json={"role": "HOD"},
    )
    assert r2.status_code == 400


def test_forged_jwt_role_cannot_become_admin(client_db):
    """JWT may claim ADMINISTRATOR, but DB role (INVIGILATOR) is authoritative."""
    c = client_db["client"]
    inv = client_db["inv"]
    forged = create_access_token(
        user_id=inv.id, email=inv.email, role="ADMINISTRATOR"
    )
    r = c.get("/admin/users", headers=_auth(forged))
    assert r.status_code == 403


def test_import_preview_and_confirm(client_db):
    c = client_db["client"]
    db = client_db["db"]
    h = _auth(client_db["token"](client_db["admin"]))
    csv_text = (
        "email,role,name,student_roll\n"
        "bulk1@gmail.com,INVIGILATOR,Bulk One,\n"
        "student@example.com,HOD,Conflict,\n"
        "bad-email,STUDENT,X,1\n"
        "dup@gmail.com,INVIGILATOR,D1,\n"
        "dup@gmail.com,INVIGILATOR,D2,\n"
        "ok.stu@students.au.edu.pk,STUDENT,OkStu,ROLL9\n"
    )
    prev = c.post(
        "/admin/users/import/preview",
        headers=h,
        files={"file": ("u.csv", io.BytesIO(csv_text.encode()), "text/csv")},
    )
    assert prev.status_code == 200
    body = prev.json()
    assert body["can_import_count"] >= 2
    assert len(body["conflicts"]) >= 1
    assert len(body["invalid"]) >= 1
    assert len(body["duplicates"]) >= 1

    conf = c.post(
        "/admin/users/import",
        headers=h,
        json={"rows": body["valid"]},
    )
    assert conf.status_code == 200
    assert conf.json()["created"] == len(body["valid"])
    assert db.scalar(select(User).where(User.email == "bulk1@gmail.com")) is not None
    # Conflict target unchanged
    assert client_db["student"].role == "STUDENT"

    bulk_audit = db.scalars(
        select(AuditLog).where(AuditLog.action == "USER_BULK_IMPORTED")
    ).first()
    assert bulk_audit is not None


def test_admin_cannot_access_ufm_cases(client_db):
    c = client_db["client"]
    h = _auth(client_db["token"](client_db["admin"]))
    r = c.get("/ufm-cases", headers=h)
    assert r.status_code == 200
    assert r.json() == []


def test_create_admin_script_safe_repeat(client_db, monkeypatch):
    from create_admin import main as create_admin_main
    import create_admin as mod

    db = client_db["db"]
    monkeypatch.setattr(mod, "SessionLocal", client_db["Session"])

    monkeypatch.setattr(
        "sys.argv",
        ["create_admin.py", "--email", "bootstrap@gmail.com", "--name", "Boot"],
    )
    create_admin_main()
    u = db.scalar(select(User).where(User.email == "bootstrap@gmail.com"))
    assert u is not None
    assert u.role == "ADMINISTRATOR"

    # Second run OK (idempotent)
    with pytest.raises(SystemExit) as ok:
        create_admin_main()
    assert ok.value.code == 0

    # Refuse promote of existing non-admin
    monkeypatch.setattr(
        "sys.argv",
        ["create_admin.py", "--email", "inv@example.com"],
    )
    with pytest.raises(SystemExit) as exc:
        create_admin_main()
    assert exc.value.code == 1
