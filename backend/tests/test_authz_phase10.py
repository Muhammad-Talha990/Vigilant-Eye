"""
Phase 10 — critical authorization tests (users IDOR, evidence, reviews).

Run from backend/:
  pytest -q tests/test_authz_phase10.py
"""

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
from models.case_review import CaseReview
from models.evidence import Evidence
from models.exam import Exam
from models.exam_room import ExamRoom
from models.student import Student
from models.ufm_case import UfmCase
from models.user import User
from security import hash_password


@pytest.fixture()
def client_and_ids(tmp_path: Path):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        student_user = User(
            name="Student A",
            email="student_a@demo.com",
            password_hash=hash_password("Demo@123"),
            role="STUDENT",
            is_active=True,
        )
        other_student_user = User(
            name="Student B",
            email="student_b@demo.com",
            password_hash=hash_password("Demo@123"),
            role="STUDENT",
            is_active=True,
        )
        invig = User(
            name="Invig Demo",
            email="invigilator@demo.com",
            password_hash=hash_password("Demo@123"),
            role="INVIGILATOR",
            is_active=True,
        )
        hod = User(
            name="HOD Demo",
            email="hod@demo.com",
            password_hash=hash_password("Demo@123"),
            role="HOD",
            is_active=True,
        )
        db.add_all([student_user, other_student_user, invig, hod])
        db.flush()

        room = ExamRoom(room_number="A-101", building="Block A", capacity=40)
        db.add(room)
        db.flush()

        student_a = Student(
            student_id="STU-A",
            name="Student A",
            department="CS",
            program="BS",
            user_id=student_user.id,
        )
        student_b = Student(
            student_id="STU-B",
            name="Student B",
            department="CS",
            program="BS",
            user_id=other_student_user.id,
        )
        db.add_all([student_a, student_b])
        db.flush()

        exam = Exam(
            course_code="CS101",
            course_name="Intro",
            semester="Fall",
            exam_date=date(2026, 1, 15),
            start_time=time(9, 0),
            end_time=time(12, 0),
            room_id=room.id,
        )
        db.add(exam)
        db.flush()

        case_a = UfmCase(
            case_number="UFM-TEST-A",
            student_id=student_a.id,
            exam_id=exam.id,
            reported_by=invig.id,
            violation_type="MOBILE_PHONE",
            description="Case A",
            status="PENDING",
            signer_name="Invig Demo",
            signature_ack=True,
        )
        case_b = UfmCase(
            case_number="UFM-TEST-B",
            student_id=student_b.id,
            exam_id=exam.id,
            reported_by=invig.id,
            violation_type="NOTES_PAPER",
            description="Case B",
            status="PENDING",
            signer_name="Invig Demo",
            signature_ack=True,
        )
        db.add_all([case_a, case_b])
        db.flush()

        evid_dir = tmp_path / "evidence"
        evid_dir.mkdir()
        file_a = evid_dir / "a.txt"
        file_b = evid_dir / "b.txt"
        file_a.write_text("evidence-a", encoding="utf-8")
        file_b.write_text("evidence-b", encoding="utf-8")

        evid_a = Evidence(
            case_id=case_a.id,
            evidence_type="DOCUMENT",
            file_path=str(file_a),
            uploaded_by=invig.id,
            is_demo=False,
        )
        evid_b = Evidence(
            case_id=case_b.id,
            evidence_type="DOCUMENT",
            file_path=str(file_b),
            uploaded_by=invig.id,
            is_demo=False,
        )
        db.add_all([evid_a, evid_b])
        db.flush()

        review = CaseReview(
            case_id=case_a.id,
            reviewer_id=hod.id,
            reviewer_role="HOD",
            action="FORWARD",
            remarks="Internal staff remarks — must not leak to student",
            signer_name="HOD Demo",
            signature_ack=True,
        )
        db.add(review)
        db.commit()

        ids = {
            "student_a_user_id": student_user.id,
            "student_b_user_id": other_student_user.id,
            "invig_id": invig.id,
            "hod_id": hod.id,
            "case_a_id": case_a.id,
            "case_b_id": case_b.id,
            "evid_a_id": evid_a.id,
            "evid_b_id": evid_b.id,
        }
    finally:
        db.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c, ids
    app.dependency_overrides.clear()


def _login(client: TestClient, email: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": "Demo@123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_student_cannot_get_another_user_profile(client_and_ids):
    client, ids = client_and_ids
    headers = _login(client, "student_a@demo.com")
    r = client.get(f"/users/{ids['invig_id']}", headers=headers)
    assert r.status_code == 403


def test_student_can_get_own_user_profile(client_and_ids):
    client, ids = client_and_ids
    headers = _login(client, "student_a@demo.com")
    r = client.get(f"/users/{ids['student_a_user_id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "student_a@demo.com"
    assert r.json()["role"] == "STUDENT"


def test_staff_can_get_user_by_id(client_and_ids):
    client, ids = client_and_ids
    headers = _login(client, "hod@demo.com")
    r = client.get(f"/users/{ids['invig_id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "invigilator@demo.com"


def test_student_evidence_own_case_allowed(client_and_ids):
    client, ids = client_and_ids
    headers = _login(client, "student_a@demo.com")
    listed = client.get(
        f"/evidence?case_id={ids['case_a_id']}", headers=headers
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == ids["evid_a_id"]

    file_r = client.get(
        f"/evidence/{ids['evid_a_id']}/file", headers=headers
    )
    assert file_r.status_code == 200
    assert b"evidence-a" in file_r.content


def test_student_cannot_access_other_student_evidence(client_and_ids):
    client, ids = client_and_ids
    headers = _login(client, "student_a@demo.com")

    listed = client.get(
        f"/evidence?case_id={ids['case_b_id']}", headers=headers
    )
    assert listed.status_code == 403

    file_r = client.get(
        f"/evidence/{ids['evid_b_id']}/file", headers=headers
    )
    assert file_r.status_code == 403

    preview_r = client.get(
        f"/evidence/{ids['evid_b_id']}/preview", headers=headers
    )
    assert preview_r.status_code == 403

    # Unscoped list must not include other student's evidence
    all_listed = client.get("/evidence", headers=headers)
    assert all_listed.status_code == 200
    ids_seen = {row["id"] for row in all_listed.json()}
    assert ids["evid_a_id"] in ids_seen
    assert ids["evid_b_id"] not in ids_seen


def test_staff_can_access_any_evidence(client_and_ids):
    client, ids = client_and_ids
    headers = _login(client, "invigilator@demo.com")
    for evid_id in (ids["evid_a_id"], ids["evid_b_id"]):
        r = client.get(f"/evidence/{evid_id}/file", headers=headers)
        assert r.status_code == 200
    listed = client.get("/evidence", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) >= 2


def test_student_denied_case_reviews(client_and_ids):
    client, ids = client_and_ids
    headers = _login(client, "student_a@demo.com")
    r = client.get(
        f"/ufm-cases/{ids['case_a_id']}/reviews", headers=headers
    )
    assert r.status_code == 403
    # ID swap must not bypass
    r2 = client.get(
        f"/ufm-cases/{ids['case_b_id']}/reviews", headers=headers
    )
    assert r2.status_code == 403


def test_staff_can_list_case_reviews(client_and_ids):
    client, ids = client_and_ids
    headers = _login(client, "hod@demo.com")
    r = client.get(
        f"/ufm-cases/{ids['case_a_id']}/reviews", headers=headers
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["action"] == "FORWARD"
    assert "Internal staff remarks" in (body[0]["remarks"] or "")


def test_student_cannot_get_other_case(client_and_ids):
    client, ids = client_and_ids
    headers = _login(client, "student_a@demo.com")
    r = client.get(f"/ufm-cases/{ids['case_b_id']}", headers=headers)
    assert r.status_code == 403
