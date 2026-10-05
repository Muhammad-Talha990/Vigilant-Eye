"""
C28 — Evidence upload is Invigilator-only; reviewers retain view access.

Run from backend/:
  pytest -q tests/test_evidence_upload_c28.py
"""

from __future__ import annotations

from datetime import date, time
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from case_access import EVIDENCE_UPLOAD_ROLES, MONITOR_ROLES
from database import get_db
from main import app
from models.base import Base
from models.evidence import Evidence
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

    room = ExamRoom(room_number="C28-R1", building="A", capacity=40)
    db.add(room)
    db.commit()
    db.refresh(room)

    users = {
        role: add_user(email=f"{role.lower()}.c28@demo.com", role=role)
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
        student_id="C28STU01",
        name="C28 Student",
        department="CS",
        program="BSCS",
        user_id=users["STUDENT"].id,
    )
    exam = Exam(
        course_code="C28101",
        course_name="C28 Exam",
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
        case_number="UFM-C28-001",
        student_id=student.id,
        exam_id=exam.id,
        reported_by=users["INVIGILATOR"].id,
        violation_type="MOBILE_PHONE",
        description="C28 evidence case",
        status="PENDING",
        signer_name="Inv C28",
        signature_ack=True,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    existing = Evidence(
        case_id=case.id,
        detection_id=None,
        evidence_type="SNAPSHOT",
        file_path="uploads/evidence/c28-existing.webp",
        camera_id=None,
        seat_location=None,
        confidence=0.9,
        uploaded_by=users["INVIGILATOR"].id,
    )
    db.add(existing)
    db.commit()
    db.refresh(existing)

    def token(user: User) -> str:
        return create_access_token(
            user_id=user.id, email=user.email, role=user.role
        )

    client = TestClient(app)
    yield {
        "client": client,
        "token": token,
        "users": users,
        "case": case,
        "evidence": existing,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _upload_body(case_id: int):
    return {
        "case_id": str(case_id),
        "evidence_type": "DOCUMENT",
    }


def test_upload_roles_invigilator_only():
    assert EVIDENCE_UPLOAD_ROLES == frozenset({"INVIGILATOR"})
    assert MONITOR_ROLES == frozenset({"INVIGILATOR"})
    ra = (FE / "config" / "roleAccess.js").read_text(encoding="utf-8")
    upload = ra.split("export const EVIDENCE_UPLOAD_ROLES")[1].split(
        "export const EVIDENCE_VIEW_ROLES"
    )[0]
    view = ra.split("export const EVIDENCE_VIEW_ROLES")[1].split(
        "export const MASTER_DATA_VIEW_ROLES"
    )[0]
    assert '"INVIGILATOR"' in upload
    assert '"HOD"' not in upload
    assert '"HOD"' in view
    assert '"DEC"' in view


def test_invigilator_can_upload_evidence(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["users"]["INVIGILATOR"]))
    files = {"file": ("note.txt", BytesIO(b"c28 evidence"), "text/plain")}
    r = c.post(
        "/evidence",
        headers=h,
        data=_upload_body(client_db["case"].id),
        files=files,
    )
    assert r.status_code == 201, r.text
    assert r.json()["case_id"] == client_db["case"].id


def test_non_creators_cannot_upload_evidence(client_db):
    c = client_db["client"]
    for role in (
        "HOD",
        "DEC",
        "EXAM_DEPARTMENT",
        "UFM_COMMITTEE",
        "STUDENT",
        "ADMINISTRATOR",
    ):
        h = _h(client_db["token"](client_db["users"][role]))
        files = {"file": ("x.txt", BytesIO(b"nope"), "text/plain")}
        r = c.post(
            "/evidence",
            headers=h,
            data=_upload_body(client_db["case"].id),
            files=files,
        )
        assert r.status_code == 403, f"{role}: {r.text}"


def test_reviewers_can_view_existing_evidence(client_db):
    c = client_db["client"]
    eid = client_db["evidence"].id
    case_id = client_db["case"].id
    for role in ("HOD", "DEC", "EXAM_DEPARTMENT", "UFM_COMMITTEE", "INVIGILATOR"):
        h = _h(client_db["token"](client_db["users"][role]))
        listed = c.get(f"/evidence?case_id={case_id}", headers=h)
        assert listed.status_code == 200, f"{role}: {listed.text}"
        ids = {row["id"] for row in listed.json()}
        assert eid in ids


def test_hod_c26_still_denied_monitor_create(client_db):
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


def test_evidence_page_upload_gated_to_upload_roles():
    src = (FE / "pages" / "EvidencePage.jsx").read_text(encoding="utf-8")
    assert "EVIDENCE_UPLOAD_ROLES" in src
    assert "canUpload" in src
    assert "Upload evidence" in src
    assert "Invigilator accounts" in src
    detail = (FE / "pages" / "CaseDetailPage.jsx").read_text(encoding="utf-8")
    assert "View evidence" in detail
    assert "canUploadEvidence" in detail
