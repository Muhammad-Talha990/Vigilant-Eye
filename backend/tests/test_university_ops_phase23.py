"""
Phase 23 — University operational readiness: exam ops, idempotency, role boundaries.
"""

from __future__ import annotations

from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models.base import Base
from models.clarification import Clarification
from models.detection import Detection
from models.exam import Exam
from models.exam_enrollment import ExamEnrollment
from models.exam_invigilator import ExamInvigilator
from models.exam_room import ExamRoom
from models.student import Student
from models.ufm_case import UfmCase
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
        except Exception:
            db.rollback()
            raise
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

    admin = add_user(email="admin23@example.com", role="ADMINISTRATOR")
    inv = add_user(email="inv23@example.com", role="INVIGILATOR")
    hod = add_user(email="hod23@example.com", role="HOD")
    dec = add_user(email="dec23@example.com", role="DEC")
    exam_u = add_user(email="exam23@example.com", role="EXAM_DEPARTMENT")
    ufm = add_user(email="ufm23@example.com", role="UFM_COMMITTEE")
    stu_user = add_user(email="stu23@students.au.edu.pk", role="STUDENT")

    room = ExamRoom(room_number="R23", building="A", capacity=40)
    db.add(room)
    db.commit()
    db.refresh(room)

    exam = Exam(
        course_code="CS23",
        course_name="Ops Test",
        semester="Spring 2026",
        exam_date=date(2026, 6, 1),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    db.add(exam)
    student = Student(
        student_id="ROLL23",
        name="Stu23",
        department="CS",
        program="BSCS",
        user_id=stu_user.id,
    )
    db.add(student)
    db.commit()
    db.refresh(exam)
    db.refresh(student)

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
        "inv": inv,
        "hod": hod,
        "dec": dec,
        "exam_u": exam_u,
        "ufm": ufm,
        "stu_user": stu_user,
        "room": room,
        "exam": exam,
        "student": student,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_exam_update_and_invalid_times(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["hod"]))
    exam = client_db["exam"]
    bad = c.patch(
        f"/exams/{exam.id}",
        headers=h,
        json={"start_time": "14:00:00", "end_time": "13:00:00"},
    )
    assert bad.status_code == 400
    ok = c.patch(
        f"/exams/{exam.id}",
        headers=h,
        json={"course_name": "Ops Test Updated"},
    )
    assert ok.status_code == 200
    assert ok.json()["course_name"] == "Ops Test Updated"


def test_enrollment_enforced_when_roster_present(client_db):
    c = client_db["client"]
    db = client_db["db"]
    h = _h(client_db["token"](client_db["exam_u"]))
    exam = client_db["exam"]
    student = client_db["student"]

    # Empty roster — case create allowed
    r = c.post(
        "/ufm-cases",
        headers=_h(client_db["token"](client_db["inv"])),
        json={
            "student_id": student.id,
            "exam_id": exam.id,
            "violation_type": "MOBILE_PHONE",
            "description": "Phone visible",
            "signer_name": "Inv 23",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201

    # Enroll then reject other student
    other = Student(
        student_id="OTHER23",
        name="Other",
        department="CS",
        program="BSCS",
    )
    db.add(other)
    db.commit()
    db.refresh(other)

    en = c.post(
        f"/exams/{exam.id}/enrollments",
        headers=h,
        json={"student_id": student.id},
    )
    assert en.status_code == 201

    denied = c.post(
        "/ufm-cases",
        headers=_h(client_db["token"](client_db["inv"])),
        json={
            "student_id": other.id,
            "exam_id": exam.id,
            "violation_type": "NOTES_PAPER",
            "description": "Notes",
            "signer_name": "Inv 23",
            "signature_ack": True,
        },
    )
    assert denied.status_code == 400
    assert "not enrolled" in denied.json()["detail"].lower()


def test_invigilator_assignment(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["hod"]))
    exam = client_db["exam"]
    inv = client_db["inv"]
    r = c.post(
        f"/exams/{exam.id}/invigilators",
        headers=h,
        json={"user_id": inv.id},
    )
    assert r.status_code == 201
    listed = c.get(f"/exams/{exam.id}/invigilators", headers=h)
    assert listed.status_code == 200
    assert any(row["user_id"] == inv.id for row in listed.json())
    # Non-invigilator rejected
    bad = c.post(
        f"/exams/{exam.id}/invigilators",
        headers=h,
        json={"user_id": client_db["hod"].id},
    )
    assert bad.status_code == 400


def test_clarification_idempotent(client_db):
    c = client_db["client"]
    db = client_db["db"]
    case = UfmCase(
        case_number="UFM-20260601-0099",
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        violation_type="MOBILE_PHONE",
        description="x",
        status="PENDING",
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    h = _h(client_db["token"](client_db["stu_user"]))
    first = c.post(
        "/clarifications",
        headers=h,
        json={"case_id": case.id, "statement": "I did not cheat."},
    )
    assert first.status_code == 201
    second = c.post(
        "/clarifications",
        headers=h,
        json={"case_id": case.id, "statement": "This is a second attempt which should fail."},
    )
    assert second.status_code == 400


def test_admin_denied_operational_audit(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    assert c.get("/audit-logs", headers=h).status_code == 403
    assert c.get("/ufm-cases", headers=h).status_code == 200
    assert c.get("/ufm-cases", headers=h).json() == []
    assert c.get("/live/status", headers=h).status_code == 403


@pytest.mark.parametrize(
    "role_key,allowed_exams,allowed_admin",
    [
        ("inv", True, False),
        ("hod", True, False),
        ("dec", True, False),
        ("exam_u", True, False),
        ("ufm", False, False),
        ("stu_user", False, False),
        ("admin", False, True),
    ],
)
def test_role_matrix_exams_vs_admin(client_db, role_key, allowed_exams, allowed_admin):
    c = client_db["client"]
    h = _h(client_db["token"](client_db[role_key]))
    exams = c.get("/exams", headers=h)
    assert exams.status_code == (200 if allowed_exams else 403)
    admin_users = c.get("/admin/users", headers=h)
    assert admin_users.status_code == (200 if allowed_admin else 403)


def test_alembic_head_includes_exam_ops():
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    # Head advanced by AI detection model_version migration.
    assert script.get_current_head() == "20261004_0006_detection_model_version"
    revs = {r.revision for r in script.walk_revisions()}
    assert "20260928_0003_exam_ops" in revs
    assert "20260930_0004_ufm_form" in revs
    assert "20260930_0005_case_camera" in revs
    assert "20261004_0006_detection_model_version" in revs


def test_exam_detail_includes_room_cameras(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.get(f"/exams/{client_db['exam'].id}", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "enrollments" in body
    assert "invigilators" in body
    assert "room_cameras" in body
