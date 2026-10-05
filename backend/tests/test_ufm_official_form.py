"""Official AU UFM form — recovered materials + create validation."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models.base import Base
from models.exam import Exam
from models.exam_room import ExamRoom
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
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    db = TestingSession()

    room = ExamRoom(room_number="UFM-R1", building="Block A", capacity=40)
    db.add(room)
    db.commit()
    db.refresh(room)

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

    inv = add_user(email="invig.ufm.form@demo.com", role="INVIGILATOR", name="Invig Form")
    student_user = add_user(
        email="student.ufm.form@demo.com", role="STUDENT", name="Student Form"
    )
    admin = add_user(
        email="admin.ufm.form@demo.com", role="ADMINISTRATOR", name="Admin Form"
    )

    student = Student(
        student_id="UFMFORM01",
        name="Form Student",
        department="CS",
        program="BSCS",
        user_id=student_user.id,
    )
    exam = Exam(
        course_code="UFM101",
        course_name="UFM Form Exam",
        semester="Fall",
        exam_date=date(2026, 6, 1),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    db.add_all([student, exam])
    db.commit()
    db.refresh(student)
    db.refresh(exam)

    def token(user: User) -> str:
        return create_access_token(
            user_id=user.id, email=user.email, role=user.role
        )

    client = TestClient(app)
    yield {
        "client": client,
        "db": db,
        "token": token,
        "inv": inv,
        "admin": admin,
        "student_user": student_user,
        "student": student,
        "exam": exam,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_create_case_with_recovered_materials(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    student = client_db["student"]
    exam = client_db["exam"]

    r = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "student_id": student.id,
            "exam_id": exam.id,
            "violation_type": "OTHER",
            "description": "Mobile phone recovered under desk.",
            "recovered_materials": ["MOBILE_PHONE", "ANSWER_EXTRA_SHEET"],
            "signer_name": "Invig Form",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["violation_type"] == "MOBILE_PHONE"
    assert body["recovered_materials"] == ["MOBILE_PHONE", "ANSWER_EXTRA_SHEET"]
    assert body["recovered_other_detail"] is None

    got = c.get(f"/ufm-cases/{body['id']}", headers=h)
    assert got.status_code == 200
    assert got.json()["recovered_materials"] == [
        "MOBILE_PHONE",
        "ANSWER_EXTRA_SHEET",
    ]


def test_other_material_requires_detail(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    student = client_db["student"]
    exam = client_db["exam"]

    missing = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "student_id": student.id,
            "exam_id": exam.id,
            "violation_type": "OTHER",
            "description": "Other material without explanation.",
            "recovered_materials": ["OTHER"],
            "signer_name": "Invig Form",
            "signature_ack": True,
        },
    )
    assert missing.status_code == 422

    ok = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "student_id": student.id,
            "exam_id": exam.id,
            "violation_type": "OTHER",
            "description": "Other material with explanation.",
            "recovered_materials": ["OTHER"],
            "recovered_other_detail": "Printed formula sheet in sleeve",
            "signer_name": "Invig Form",
            "signature_ack": True,
        },
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["recovered_other_detail"] == "Printed formula sheet in sleeve"
    assert ok.json()["violation_type"] == "OTHER"


def test_invalid_recovered_material_rejected(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "Bad category",
            "recovered_materials": ["LASER_POINTER"],
            "signer_name": "Invig Form",
            "signature_ack": True,
        },
    )
    assert r.status_code == 422


def test_student_cannot_create_ufm_case(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["student_user"]))
    r = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "Should be denied",
            "signer_name": "Student",
            "signature_ack": True,
        },
    )
    assert r.status_code == 403


def test_administrator_cannot_create_ufm_case(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    r = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "Admin must not create operational UFM cases",
            "signer_name": "Admin",
            "signature_ack": True,
        },
    )
    assert r.status_code == 403


def test_legacy_create_without_recovered_materials_still_works(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
            "violation_type": "SMART_WATCH",
            "description": "Legacy payload without recovered checklist.",
            "signer_name": "Invig Form",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["violation_type"] == "SMART_WATCH"
    assert r.json()["recovered_materials"] is None


def test_alembic_head_includes_ufm_form():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    assert script.get_current_head() == "20261004_0006_detection_model_version"
