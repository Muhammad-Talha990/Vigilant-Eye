"""C16 — Result control enrichment, lifecycle clarity, and RBAC."""

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
from models.exam import Exam
from models.exam_room import ExamRoom
from models.result_control import ResultControl
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

    room = ExamRoom(room_number="C16-R1", building="Block A", capacity=40)
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

    inv = add_user(email="inv.c16@demo.com", role="INVIGILATOR", name="Inv C16")
    hod = add_user(email="hod.c16@demo.com", role="HOD", name="Hod C16")
    dec = add_user(email="dec.c16@demo.com", role="DEC", name="Dec C16")
    exam = add_user(email="exam.c16@demo.com", role="EXAM_DEPARTMENT", name="Exam C16")
    ufm = add_user(email="ufm.c16@demo.com", role="UFM_COMMITTEE", name="Ufm C16")
    stu_user = add_user(email="stu.c16@demo.com", role="STUDENT", name="Stu C16")

    student = Student(
        student_id="C16STU01",
        name="C16 Student",
        department="CS",
        program="BSCS",
        user_id=stu_user.id,
    )
    exam_row = Exam(
        course_code="C16101",
        course_name="C16 Exam",
        semester="Fall",
        exam_date=date(2026, 10, 1),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    db.add_all([student, exam_row])
    db.commit()
    db.refresh(student)
    db.refresh(exam_row)

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
        "hod": hod,
        "dec": dec,
        "exam": exam,
        "ufm": ufm,
        "stu_user": stu_user,
        "student": student,
        "exam_row": exam_row,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _sign(action: str, remarks: str = "ok") -> dict:
    return {
        "action": action,
        "remarks": remarks,
        "signer_name": "C16 Tester",
        "signature_ack": True,
    }


def _create_case(client_db) -> int:
    c = client_db["client"]
    r = c.post(
        "/ufm-cases",
        headers=_h(client_db["token"](client_db["inv"])),
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam_row"].id,
            "violation_type": "OTHER",
            "description": "C16 fixture case",
            "signer_name": "Invigilator",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _advance_to_committee(client_db, case_id: int):
    c = client_db["client"]
    for role_key, action in (
        ("hod", "FORWARD"),
        ("dec", "FORWARD"),
        ("exam", "FORWARD"),
    ):
        r = c.post(
            f"/ufm-cases/{case_id}/reviews",
            headers=_h(client_db["token"](client_db[role_key])),
            json=_sign(action),
        )
        assert r.status_code == 201, r.text


def test_result_controls_list_shows_student_and_case(client_db):
    c = client_db["client"]
    case_id = _create_case(client_db)
    _advance_to_committee(client_db, case_id)

    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["ufm"])),
        json=_sign("APPROVE", "sustained"),
    )
    assert r.status_code == 201, r.text

    r = c.get(
        "/result-controls",
        headers=_h(client_db["token"](client_db["exam"])),
    )
    assert r.status_code == 200
    rows = r.json()
    assert rows
    row = next(x for x in rows if x["case_id"] == case_id)
    assert row["result_status"] == "HELD"
    assert row["student_name"] == "C16 Student"
    assert row["student_roll"] == "C16STU01"
    assert row["case_number"]
    assert row["case_status"] == "APPROVED"
    assert "Automatic hold" in (row["reason"] or "")
    assert row["hold_source"] == "AUTOMATIC_APPROVE"
    assert row["held_by_name"] == "Ufm C16"
    assert row["held_at"] is not None


def test_case_detail_includes_result_control_summary(client_db):
    c = client_db["client"]
    case_id = _create_case(client_db)
    _advance_to_committee(client_db, case_id)
    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["ufm"])),
        json=_sign("APPROVE"),
    )
    assert r.status_code == 201

    for role_key in ("exam", "ufm", "hod", "inv", "stu_user"):
        r = c.get(
            f"/ufm-cases/{case_id}",
            headers=_h(client_db["token"](client_db[role_key])),
        )
        assert r.status_code == 200, role_key
        rc = r.json().get("result_control")
        assert rc is not None, role_key
        assert rc["result_status"] == "HELD"
        assert rc["case_id"] == case_id


def test_return_does_not_create_result_hold(client_db):
    c = client_db["client"]
    case_id = _create_case(client_db)
    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["hod"])),
        json=_sign("FORWARD"),
    )
    assert r.status_code == 201
    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["dec"])),
        json=_sign("RETURN", "need more detail"),
    )
    assert r.status_code == 201
    db = client_db["db"]
    db.expire_all()
    hold = db.scalar(select(ResultControl).where(ResultControl.case_id == case_id))
    assert hold is None
    case = db.get(UfmCase, case_id)
    assert case.status == "PENDING"


def test_reject_does_not_create_result_hold(client_db):
    c = client_db["client"]
    case_id = _create_case(client_db)
    _advance_to_committee(client_db, case_id)
    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["ufm"])),
        json=_sign("REJECT", "not sustained"),
    )
    assert r.status_code == 201
    db = client_db["db"]
    db.expire_all()
    hold = db.scalar(select(ResultControl).where(ResultControl.case_id == case_id))
    assert hold is None
    case = db.get(UfmCase, case_id)
    assert case.status == "REJECTED"

    r = c.get(
        f"/ufm-cases/{case_id}",
        headers=_h(client_db["token"](client_db["exam"])),
    )
    assert r.status_code == 200
    assert r.json().get("result_control") is None


def test_release_authorized_and_denied(client_db):
    c = client_db["client"]
    case_id = _create_case(client_db)
    _advance_to_committee(client_db, case_id)
    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["ufm"])),
        json=_sign("APPROVE"),
    )
    assert r.status_code == 201
    db = client_db["db"]
    hold = db.scalar(select(ResultControl).where(ResultControl.case_id == case_id))
    assert hold is not None

    r = c.patch(
        f"/result-controls/{hold.id}/release",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r.status_code == 403

    r = c.patch(
        f"/result-controls/{hold.id}/release",
        headers=_h(client_db["token"](client_db["exam"])),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["result_status"] == "RELEASED"
    assert body["transcript_status"] == "ALLOWED"
    assert body["released_by_name"] == "Exam C16"
    assert body["student_name"] == "C16 Student"


def test_result_controls_page_student_first_ux_markers():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "frontend" / "src"
    page = (root / "pages" / "ResultControlsPage.jsx").read_text(encoding="utf-8")
    detail = (root / "pages" / "CaseDetailPage.jsx").read_text(encoding="utf-8")
    assert "Affected students" in page
    assert "Release Result Hold" in page
    assert "portal-data-cards" in page
    assert "portal-table-desktop" in page
    assert "Search student" in page
    assert "Result control" in detail
    assert "formatResultStatusLabel" in detail
    assert "Release Result Hold" in detail
    assert "Place Result Hold" not in page
