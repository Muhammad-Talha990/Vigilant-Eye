"""
C31 — HOD review queue must include PENDING and UNDER_REVIEW (C22 active queue).

Regression: HOD "Cases for Review" used ?status=PENDING only. Opening a case
promotes PENDING → UNDER_REVIEW while HOD remains owner, so the queue looked empty.

  pytest -q tests/test_hod_queue_c31.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from case_access import ACTIVE_QUEUE_STATUSES_BY_ROLE, case_list_statuses_for_role
from database import get_db
from main import app
from models.base import Base
from models.exam import Exam
from models.exam_room import ExamRoom
from models.student import Student
from models.ufm_case import UfmCase
from models.user import User
from security import create_access_token, hash_password
from workflow import next_status

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend" / "src"


@pytest.fixture()
def client_db():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    users = {}
    for key, role, email in [
        ("inv", "INVIGILATOR", "c31-inv@test.local"),
        ("hod", "HOD", "c31-hod@test.local"),
        ("dec", "DEC", "c31-dec@test.local"),
        ("exam", "EXAM_DEPARTMENT", "c31-exam@test.local"),
        ("ufm", "UFM_COMMITTEE", "c31-ufm@test.local"),
    ]:
        u = User(
            name=f"C31 {role}",
            email=email,
            password_hash=hash_password("Demo@12345"),
            role=role,
            is_active=True,
        )
        db.add(u)
        users[key] = u
    db.flush()

    room = ExamRoom(room_number="C31-R1", building="A", capacity=40)
    db.add(room)
    db.flush()
    student = Student(
        student_id="C31-ROLL",
        name="C31 Student",
        department="CS",
        program="BSCS",
    )
    exam = Exam(
        course_code="C31EX",
        course_name="C31 Exam",
        semester="Fall",
        exam_date=datetime(2026, 10, 4).date(),
        start_time=datetime(2026, 10, 4, 9, 0).time(),
        end_time=datetime(2026, 10, 4, 12, 0).time(),
        room_id=room.id,
    )
    db.add_all([student, exam])
    db.flush()

    def add_case(suffix: str, status: str) -> UfmCase:
        c = UfmCase(
            case_number=f"UFM-C31-{suffix}",
            student_id=student.id,
            exam_id=exam.id,
            reported_by=users["inv"].id,
            violation_type="MOBILE_PHONE",
            description=f"C31 {suffix}",
            status=status,
            created_at=datetime(2026, 10, 4, 10, 0, 0),
            updated_at=datetime(2026, 10, 4, 10, 0, 0),
            signer_name="C31 Inv",
            signed_at=datetime(2026, 10, 4, 10, 0, 0),
            signature_ack=True,
        )
        db.add(c)
        db.flush()
        return c

    fixtures = {
        "pending": add_case("P", "PENDING"),
        "under": add_case("U", "UNDER_REVIEW"),
        "dec": add_case("D", "DEC_REVIEW"),
        "exam": add_case("E", "EXAM_DEPARTMENT_REVIEW"),
        "ufm": add_case("C", "UFM_COMMITTEE_REVIEW"),
        "approved": add_case("A", "APPROVED"),
        "rejected": add_case("R", "REJECTED"),
    }
    db.commit()

    def _get_db():
        s = TestingSessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    client = TestClient(app)

    def token(key: str) -> str:
        u = users[key]
        return create_access_token(user_id=u.id, email=u.email, role=u.role)

    yield {
        "client": client,
        "db": db,
        "users": users,
        "token": token,
        "fixtures": fixtures,
        "student": student,
        "exam": exam,
    }
    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _ids(rows: list[dict]) -> set[int]:
    return {int(r["id"]) for r in rows}


def test_hod_active_queue_includes_pending_and_under_review(client_db):
    assert ACTIVE_QUEUE_STATUSES_BY_ROLE["HOD"] == frozenset(
        {"PENDING", "UNDER_REVIEW"}
    )
    c = client_db["client"]
    h = _h(client_db["token"]("hod"))
    r = c.get("/ufm-cases?scope=active", headers=h)
    assert r.status_code == 200
    ids = _ids(r.json())
    fx = client_db["fixtures"]
    assert fx["pending"].id in ids
    assert fx["under"].id in ids
    assert fx["dec"].id not in ids
    assert fx["exam"].id not in ids
    assert fx["ufm"].id not in ids
    assert fx["approved"].id not in ids
    assert fx["rejected"].id not in ids


def test_hod_pending_status_filter_excludes_under_review(client_db):
    """status=PENDING alone is valid but incomplete for the HOD review nav."""
    c = client_db["client"]
    h = _h(client_db["token"]("hod"))
    r = c.get("/ufm-cases?scope=dashboard&status=PENDING", headers=h)
    assert r.status_code == 200
    ids = _ids(r.json())
    fx = client_db["fixtures"]
    assert fx["pending"].id in ids
    assert fx["under"].id not in ids


def test_new_pending_case_visible_to_hod_active_queue(client_db):
    c = client_db["client"]
    inv_h = _h(client_db["token"]("inv"))
    hod_h = _h(client_db["token"]("hod"))
    r = c.post(
        "/ufm-cases",
        headers=inv_h,
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "C31 newly created pending",
            "recovered_materials": ["MOBILE_PHONE"],
            "signer_name": "C31 Invigilator",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text
    case = r.json()
    assert case["status"] == "PENDING"
    case_id = case["id"]

    active = c.get("/ufm-cases?scope=active", headers=hod_h)
    assert active.status_code == 200
    assert case_id in _ids(active.json())

    pending = c.get("/ufm-cases?scope=dashboard&status=PENDING", headers=hod_h)
    assert case_id in _ids(pending.json())


def test_hod_open_promotes_pending_but_stays_in_active_queue(client_db):
    c = client_db["client"]
    hod_h = _h(client_db["token"]("hod"))
    pending_id = client_db["fixtures"]["pending"].id

    before = c.get("/ufm-cases?scope=active", headers=hod_h).json()
    assert pending_id in _ids(before)

    opened = c.get(f"/ufm-cases/{pending_id}", headers=hod_h)
    assert opened.status_code == 200
    assert opened.json()["status"] == "UNDER_REVIEW"

    # PENDING-only filter no longer includes it (the C31 user-facing bug).
    pending_only = c.get(
        "/ufm-cases?scope=dashboard&status=PENDING", headers=hod_h
    ).json()
    assert pending_id not in _ids(pending_only)

    # Active queue still includes UNDER_REVIEW HOD work.
    after = c.get("/ufm-cases?scope=active", headers=hod_h).json()
    assert pending_id in _ids(after)


def test_return_to_pending_reappears_for_hod(client_db):
    c = client_db["client"]
    hod_h = _h(client_db["token"]("hod"))
    dec_h = _h(client_db["token"]("dec"))
    under_id = client_db["fixtures"]["under"].id

    # HOD forwards UNDER_REVIEW → DEC_REVIEW
    r = c.post(
        f"/ufm-cases/{under_id}/reviews",
        headers=hod_h,
        json={
            "action": "FORWARD",
            "remarks": "to DEC",
            "signer_name": "C31 HOD",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text
    assert (
        next_status(
            role="HOD", action="FORWARD", current_status="UNDER_REVIEW"
        )
        == "DEC_REVIEW"
    )

    hod_active = _ids(c.get("/ufm-cases?scope=active", headers=hod_h).json())
    assert under_id not in hod_active
    dec_active = _ids(c.get("/ufm-cases?scope=active", headers=dec_h).json())
    assert under_id in dec_active

    # DEC returns → PENDING
    r = c.post(
        f"/ufm-cases/{under_id}/reviews",
        headers=dec_h,
        json={
            "action": "RETURN",
            "remarks": "back to HOD",
            "signer_name": "C31 DEC",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text

    hod_active = _ids(c.get("/ufm-cases?scope=active", headers=hod_h).json())
    assert under_id in hod_active
    dec_active = _ids(c.get("/ufm-cases?scope=active", headers=dec_h).json())
    assert under_id not in dec_active


def test_dec_cannot_pull_pending_via_status_filter(client_db):
    c = client_db["client"]
    h = _h(client_db["token"]("dec"))
    r = c.get("/ufm-cases?scope=dashboard&status=PENDING", headers=h)
    assert r.status_code == 200
    assert r.json() == []


def test_frontend_hod_review_links_use_scope_active():
    nav = (FE / "config" / "navByRole.js").read_text(encoding="utf-8")
    dash = (FE / "config" / "dashboardByRole.js").read_text(encoding="utf-8")
    cases = (FE / "pages" / "CasesPage.jsx").read_text(encoding="utf-8")
    hod_nav = nav.split("HOD: [")[1].split("DEC: [")[0]
    assert "/app/cases?scope=active" in hod_nav
    assert 'to: "/app/cases?status=PENDING"' not in hod_nav
    assert "/app/cases?scope=active" in dash
    assert 'viewAll: "/app/cases?status=PENDING"' not in dash
    assert 'searchParams.get("scope") === "active"' in cases
    assert 'scope: listScope' in cases


def test_hod_dashboard_count_matches_active_queue(client_db):
    """KPI dataset (PENDING+UNDER_REVIEW) equals scope=active count."""
    c = client_db["client"]
    h = _h(client_db["token"]("hod"))
    active = c.get("/ufm-cases?scope=active", headers=h).json()
    dash = c.get("/ufm-cases?scope=dashboard", headers=h).json()
    hod_owned = [
        x
        for x in dash
        if x["status"] in ACTIVE_QUEUE_STATUSES_BY_ROLE["HOD"]
    ]
    assert len(active) == len(hod_owned)
    assert _ids(active) == _ids(hod_owned)
    assert case_list_statuses_for_role("HOD") is not None
