"""
Phase 20 — Administrator portal usability & production-ready user management.
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

    admin = add_user(email="admin20@example.com", role="ADMINISTRATOR", name="Admin20")
    student = add_user(email="stu20@example.com", role="STUDENT", name="Stu20")
    inv = add_user(email="inv20@example.com", role="INVIGILATOR")
    hod = add_user(email="hod20@example.com", role="HOD")
    dec = add_user(email="dec20@example.com", role="DEC")
    exam = add_user(email="exam20@example.com", role="EXAM_DEPARTMENT")
    ufm = add_user(email="ufm20@example.com", role="UFM_COMMITTEE")
    inactive_admin = add_user(
        email="inactive.admin20@example.com",
        role="ADMINISTRATOR",
        active=False,
    )

    st = Student(
        student_id="ROLL20",
        name="Stu20",
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
        "inactive_admin": inactive_admin,
        "Session": TestingSession,
        "add_user": add_user,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_admin_dashboard_stats_and_catalog(client_db):
    c = client_db["client"]
    h = _auth(client_db["token"](client_db["admin"]))
    stats = c.get("/admin/users/stats", headers=h)
    assert stats.status_code == 200
    body = stats.json()
    assert body["total"] >= 7
    assert "by_role" in body
    assert "ADMINISTRATOR" in body["by_role"]
    assert "STUDENT" in body["by_role"]

    roles = c.get("/admin/roles", headers=h)
    assert roles.status_code == 200
    assert any(r["role"] == "ADMINISTRATOR" for r in roles.json())

    sysinfo = c.get("/admin/system-info", headers=h)
    assert sysinfo.status_code == 200
    info = sysinfo.json()
    assert info["api_available"] is True
    assert info["database_available"] is True
    blob = str(info).lower()
    assert "jwt_secret" not in blob
    assert "postgres_password" not in blob
    assert "smtp_password" not in blob


def test_admin_user_list_search_filter_pagination(client_db):
    c = client_db["client"]
    h = _auth(client_db["token"](client_db["admin"]))
    listed = c.get("/admin/users", headers=h, params={"page": 1, "page_size": 5})
    assert listed.status_code == 200
    data = listed.json()
    assert "items" in data and "total" in data
    assert data["page_size"] == 5
    assert len(data["items"]) <= 5

    by_email = c.get("/admin/users", headers=h, params={"q": "inv20@"})
    assert by_email.status_code == 200
    assert any(u["email"] == "inv20@example.com" for u in by_email.json()["items"])

    by_role = c.get("/admin/users", headers=h, params={"role": "HOD"})
    assert by_role.status_code == 200
    assert all(u["role"] == "HOD" for u in by_role.json()["items"])

    inactive = c.get("/admin/users", headers=h, params={"is_active": False})
    assert inactive.status_code == 200
    assert all(u["is_active"] is False for u in inactive.json()["items"])

    by_roll = c.get("/admin/users", headers=h, params={"q": "ROLL20"})
    assert by_roll.status_code == 200
    assert any(u["email"] == "stu20@example.com" for u in by_roll.json()["items"])


def test_admin_create_role_activate_deactivate_link(client_db):
    c = client_db["client"]
    db = client_db["db"]
    h = _auth(client_db["token"](client_db["admin"]))

    created = c.post(
        "/admin/users",
        headers=h,
        json={
            "email": "New.Staff@Gmail.com",
            "role": "INVIGILATOR",
            "name": "New Staff",
            "is_active": True,
        },
    )
    assert created.status_code == 201
    user = created.json()
    assert user["email"] == "new.staff@gmail.com"
    assert user["role"] == "INVIGILATOR"
    uid = user["id"]

    inactive_create = c.post(
        "/admin/users",
        headers=h,
        json={
            "email": "inactive.staff@gmail.com",
            "role": "DEC",
            "name": "Inactive Staff",
            "is_active": False,
        },
    )
    assert inactive_create.status_code == 201
    assert inactive_create.json()["is_active"] is False

    role_change = c.patch(
        f"/admin/users/{uid}",
        headers=h,
        json={"role": "HOD"},
    )
    assert role_change.status_code == 200
    assert role_change.json()["role"] == "HOD"

    deact = c.post(f"/admin/users/{uid}/deactivate", headers=h)
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    react = c.post(f"/admin/users/{uid}/activate", headers=h)
    assert react.status_code == 200
    assert react.json()["is_active"] is True

    # Student link / unlink
    stu_user = c.post(
        "/admin/users",
        headers=h,
        json={
            "email": "link.stu@students.au.edu.pk",
            "role": "STUDENT",
            "name": "Link Stu",
            "student_roll": "NEWROLL20",
        },
    )
    assert stu_user.status_code == 201
    sid = stu_user.json()["id"]
    assert stu_user.json()["student_roll"] == "NEWROLL20"

    unlink = c.patch(
        f"/admin/users/{sid}",
        headers=h,
        json={"unlink_student": True},
    )
    assert unlink.status_code == 200
    assert unlink.json()["student_roll"] is None

    relink = c.patch(
        f"/admin/users/{sid}",
        headers=h,
        json={"student_roll": "NEWROLL20"},
    )
    assert relink.status_code == 200
    assert relink.json()["student_roll"] == "NEWROLL20"

    actions = {
        a
        for a in db.scalars(select(AuditLog.action)).all()
        if a.startswith("USER_")
    }
    assert "USER_CREATED" in actions
    assert "USER_ROLE_CHANGED" in actions
    assert "USER_DEACTIVATED" in actions
    assert "USER_REACTIVATED" in actions


def test_csv_preview_and_import_buckets(client_db):
    c = client_db["client"]
    h = _auth(client_db["token"](client_db["admin"]))
    # Existing student has ROLL20 linked — student link conflict
    csv_text = (
        "email,role,name,student_roll\n"
        "ok20@gmail.com,INVIGILATOR,Ok,\n"
        "stu20@example.com,HOD,RoleConflict,\n"
        "taken.roll@students.au.edu.pk,STUDENT,Clash,ROLL20\n"
        "bad,STUDENT,X,1\n"
        "dup20@gmail.com,INVIGILATOR,D1,\n"
        "dup20@gmail.com,INVIGILATOR,D2,\n"
    )
    prev = c.post(
        "/admin/users/import/preview",
        headers=h,
        files={"file": ("u.csv", io.BytesIO(csv_text.encode()), "text/csv")},
    )
    assert prev.status_code == 200
    body = prev.json()
    assert body["can_import_count"] >= 1
    assert len(body["role_conflicts"]) >= 1
    assert len(body["student_link_problems"]) >= 1
    assert len(body["invalid"]) >= 1
    assert len(body["duplicates"]) >= 1

    conf = c.post(
        "/admin/users/import",
        headers=h,
        json={"rows": body["valid"]},
    )
    assert conf.status_code == 200
    assert conf.json()["created"] == len(body["valid"])
    assert client_db["student"].role == "STUDENT"


def test_audit_access_and_student_directory_enrichment(client_db):
    c = client_db["client"]
    h = _auth(client_db["token"](client_db["admin"]))
    audit = c.get(
        "/admin/audit-logs",
        headers=h,
        params={"limit": 10, "offset": 0, "user_admin_only": True},
    )
    assert audit.status_code == 200
    assert "items" in audit.json() and "total" in audit.json()

    stu = c.get("/admin/students", headers=h, params={"q": "ROLL20"})
    assert stu.status_code == 200
    items = stu.json()["items"]
    assert items
    row = items[0]
    assert row["linked_email"] == "stu20@example.com"
    assert row["portal_active"] is True
    assert row["portal_role"] == "STUDENT"


@pytest.mark.parametrize(
    "role_key",
    ["student", "inv", "hod", "dec", "exam", "ufm"],
)
def test_non_admin_denied_phase20(client_db, role_key):
    c = client_db["client"]
    h = _auth(client_db["token"](client_db[role_key]))
    for path in (
        "/admin/users",
        "/admin/users/stats",
        "/admin/roles",
        "/admin/system-info",
        "/admin/students",
        "/admin/audit-logs",
    ):
        assert c.get(path, headers=h).status_code == 403


def test_forged_jwt_and_inactive_admin(client_db):
    c = client_db["client"]
    inv = client_db["inv"]
    forged = create_access_token(
        user_id=inv.id, email=inv.email, role="ADMINISTRATOR"
    )
    assert c.get("/admin/users", headers=_auth(forged)).status_code == 403

    inactive = client_db["inactive_admin"]
    tok = create_access_token(
        user_id=inactive.id, email=inactive.email, role=inactive.role
    )
    # get_current_user rejects inactive accounts
    r = c.get("/admin/users", headers=_auth(tok))
    assert r.status_code in (401, 403)


def test_last_active_admin_protection(client_db):
    c = client_db["client"]
    db = client_db["db"]
    # Only one active admin (inactive_admin already inactive)
    admin = client_db["admin"]
    h = _auth(client_db["token"](admin))

    demote = c.patch(
        f"/admin/users/{admin.id}",
        headers=h,
        json={"role": "HOD"},
    )
    assert demote.status_code == 400

    deact = c.post(f"/admin/users/{admin.id}/deactivate", headers=h)
    assert deact.status_code == 400

    # With a second active admin, demotion is allowed
    other = client_db["add_user"](
        email="second.admin20@example.com", role="ADMINISTRATOR"
    )
    demote2 = c.patch(
        f"/admin/users/{admin.id}",
        headers=h,
        json={"role": "INVIGILATOR"},
    )
    assert demote2.status_code == 200
    db.refresh(admin)
    assert admin.role == "INVIGILATOR"

    # Restore for isolation of later tests in same process not needed — fixture ends.


def test_email_not_patchable(client_db):
    """Email editing is intentionally unsupported — Extra fields ignored / not applied."""
    c = client_db["client"]
    h = _auth(client_db["token"](client_db["admin"]))
    inv = client_db["inv"]
    r = c.patch(
        f"/admin/users/{inv.id}",
        headers=h,
        json={"email": "hijacked@gmail.com", "name": "Still Inv"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == inv.email
    assert r.json()["name"] == "Still Inv"
