"""
C27 — Reports access must not use MONITOR/DETECTION/CREATE role sets.

Run from backend/:
  pytest -q tests/test_reports_access_c27.py
"""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from case_access import DETECTION_STAFF_ROLES, MONITOR_ROLES, REPORTS_ROLES
from database import get_db
from main import app
from models.base import Base
from models.exam import Exam
from models.exam_room import ExamRoom
from models.student import Student
from models.ufm_case import UfmCase
from models.user import User
from security import create_access_token, hash_password

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend" / "src"


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

    room = ExamRoom(room_number="C27-R1", building="A", capacity=40)
    db.add(room)
    db.commit()
    db.refresh(room)

    users = {
        role: add_user(email=f"{role.lower()}.c27@demo.com", role=role)
        for role in (
            "INVIGILATOR",
            "HOD",
            "DEC",
            "EXAM_DEPARTMENT",
            "UFM_COMMITTEE",
            "STUDENT",
            "ADMINISTRATOR",
        )
    }
    student = Student(
        student_id="C27STU01",
        name="C27 Student",
        department="CS",
        program="BSCS",
        user_id=users["STUDENT"].id,
    )
    exam = Exam(
        course_code="C27101",
        course_name="C27 Exam",
        semester="Fall",
        exam_date=date(2026, 10, 1),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    db.add_all([student, exam])
    db.commit()
    db.refresh(student)
    db.refresh(exam)

    case = UfmCase(
        case_number="UFM-C27-001",
        student_id=student.id,
        exam_id=exam.id,
        reported_by=users["INVIGILATOR"].id,
        violation_type="MOBILE_PHONE",
        description="C27 report case",
        status="PENDING",
        signer_name="Inv C27",
        signature_ack=True,
    )
    db.add(case)
    db.commit()

    def token(user: User) -> str:
        return create_access_token(
            user_id=user.id, email=user.email, role=user.role
        )

    client = TestClient(app)
    yield {"client": client, "token": token, "users": users, "case": case}
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_reports_roles_separate_from_monitor_detect_create():
    assert "HOD" in REPORTS_ROLES
    assert "INVIGILATOR" in REPORTS_ROLES
    assert MONITOR_ROLES == frozenset({"INVIGILATOR"})
    assert DETECTION_STAFF_ROLES == frozenset({"INVIGILATOR"})
    assert "HOD" not in MONITOR_ROLES
    assert "HOD" not in DETECTION_STAFF_ROLES

    ra = (FE / "config" / "roleAccess.js").read_text(encoding="utf-8")
    mon = ra.split("MONITOR_ROLES")[1].split("DETECTION_ROLES")[0]
    det = ra.split("DETECTION_ROLES")[1].split("REPORTS_ROLES")[0]
    create = ra.split("CASE_CREATE_ROLES")[1].split("EVIDENCE_UPLOAD_ROLES")[0]
    reports = ra.split("REPORTS_ROLES")[1].split("OPERATIONAL_AUDIT_ROLES")[0]
    assert "HOD" not in mon and "HOD" not in det and "HOD" not in create
    assert "HOD" in reports and "INVIGILATOR" in reports


def test_reporting_roles_can_export_csv(client_db):
    c = client_db["client"]
    for role in (
        "INVIGILATOR",
        "HOD",
        "DEC",
        "EXAM_DEPARTMENT",
        "UFM_COMMITTEE",
    ):
        h = _h(client_db["token"](client_db["users"][role]))
        r = c.get("/ufm-cases/export.csv", headers=h)
        assert r.status_code == 200, f"{role}: {r.text}"
        assert "case_number" in r.text


def test_student_and_admin_cannot_export_csv(client_db):
    c = client_db["client"]
    for role in ("STUDENT", "ADMINISTRATOR"):
        h = _h(client_db["token"](client_db["users"][role]))
        assert c.get("/ufm-cases/export.csv", headers=h).status_code == 403


def test_hod_c26_restrictions_still_hold(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["users"]["HOD"]))
    assert c.get("/live/status", headers=h).status_code == 403
    assert c.get("/detections", headers=h).status_code == 403
    assert (
        c.post(
            "/ufm-cases",
            headers=h,
            json={
                "student_id": 1,
                "exam_id": 1,
                "violation_type": "MOBILE_PHONE",
                "description": "should fail",
                "signer_name": "Hod",
                "signature_ack": True,
            },
        ).status_code
        == 403
    )
    assert c.get("/ufm-cases/export.csv", headers=h).status_code == 200


def test_reports_page_does_not_require_detections_for_hod():
    src = (FE / "pages" / "ReportsPage.jsx").read_text(encoding="utf-8")
    assert "DETECTION_ROLES" in src
    assert "canDetect" in src
    assert "fetchDetections" in src
    assert "canDetect" in src and "? fetchDetections" in src.replace("\n", " ")
