"""C15 — UFM form search/manual filing + evidence library attach + RBAC."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
CREATE_CASE_PAGE = ROOT / "frontend" / "src" / "pages" / "CreateCasePage.jsx"


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

    room = ExamRoom(room_number="C15-R1", building="Block C", capacity=30)
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

    inv = add_user(email="inv.c15@demo.com", role="INVIGILATOR", name="Inv C15")
    hod = add_user(email="hod.c15@demo.com", role="HOD", name="Hod C15")
    dec = add_user(email="dec.c15@demo.com", role="DEC", name="Dec C15")
    exam_dept = add_user(
        email="exam.c15@demo.com", role="EXAM_DEPARTMENT", name="Exam C15"
    )
    ufm = add_user(email="ufm.c15@demo.com", role="UFM_COMMITTEE", name="Ufm C15")
    student_user = add_user(
        email="stu.c15@demo.com", role="STUDENT", name="Stu C15"
    )
    admin = add_user(
        email="admin.c15@demo.com", role="ADMINISTRATOR", name="Admin C15"
    )

    student = Student(
        student_id="C15-ROLL-99",
        name="Searchable Student",
        department="CS",
        program="BSCS",
    )
    exam = Exam(
        course_code="C15EXAM",
        course_name="C15 Exam Course",
        semester="Spring",
        exam_date=date(2026, 4, 1),
        start_time=time(10, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    db.add_all([student, exam])
    db.commit()
    db.refresh(student)
    db.refresh(exam)

    orphan = Evidence(
        case_id=None,
        detection_id=None,
        evidence_type="SNAPSHOT",
        file_path="uploads/evidence/c15-orphan.webp",
        timestamp=datetime.utcnow(),
        is_demo=False,
    )
    linked = Evidence(
        case_id=None,
        detection_id=None,
        evidence_type="CLIP",
        file_path="uploads/evidence/c15-will-link.webp",
        timestamp=datetime.utcnow(),
        is_demo=False,
    )
    db.add_all([orphan, linked])
    db.commit()
    db.refresh(orphan)
    db.refresh(linked)

    # Seed a case + linked evidence for unauthorized attach attempt later
    seed_case = UfmCase(
        case_number="UFM-C15-SEED-0001",
        student_id=student.id,
        exam_id=exam.id,
        reported_by=inv.id,
        violation_type="MOBILE_PHONE",
        description="Seed case for linked evidence",
        status="PENDING",
        signer_name="Inv C15",
        signature_ack=True,
        signed_at=datetime.utcnow(),
    )
    db.add(seed_case)
    db.commit()
    db.refresh(seed_case)
    owned = Evidence(
        case_id=seed_case.id,
        detection_id=None,
        evidence_type="DOCUMENT",
        file_path="uploads/evidence/c15-owned.txt",
        timestamp=datetime.utcnow(),
        is_demo=False,
    )
    db.add(owned)
    db.commit()
    db.refresh(owned)

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
        "exam_dept": exam_dept,
        "ufm": ufm,
        "student_user": student_user,
        "admin": admin,
        "student": student,
        "exam": exam,
        "room": room,
        "orphan": orphan,
        "owned": owned,
        "seed_case": seed_case,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_student_search_query_param(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.get("/students?q=C15-ROLL", headers=h)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["student_id"] == "C15-ROLL-99"

    empty_q = c.get("/students?q=", headers=h)
    assert empty_q.status_code == 200
    assert len(empty_q.json()) >= 1


def test_exam_search_query_param(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.get("/exams?q=C15EXAM", headers=h)
    assert r.status_code == 200
    assert any(row["course_code"] == "C15EXAM" for row in r.json())


def test_invigilator_cannot_use_master_data_student_create(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.post(
        "/students",
        headers=h,
        json={
            "student_id": "C15-BLOCKED",
            "name": "Should Fail",
            "department": "EE",
            "program": "BSEE",
        },
    )
    assert r.status_code == 403


def test_invigilator_cannot_use_master_data_exam_create(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.post(
        "/exams",
        headers=h,
        json={
            "course_code": "BLOCKED",
            "course_name": "Blocked Exam",
            "semester": "Fall",
            "exam_date": "2026-05-01",
            "start_time": "09:00:00",
            "end_time": "12:00:00",
            "room_id": client_db["room"].id,
        },
    )
    assert r.status_code == 403


def test_filing_time_manual_student_and_exam(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    before_students = client_db["db"].scalar(select(func.count()).select_from(Student))
    before_exams = client_db["db"].scalar(select(func.count()).select_from(Exam))

    r = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "manual_student": {
                "student_id": "C15-NEW-01",
                "name": "Manual Entry Student",
                "department": "EE",
                "program": "BSEE",
            },
            "manual_exam": {
                "course_code": "C15NEW",
                "course_name": "Filing Exam",
                "semester": "Fall",
                "exam_date": "2026-05-02",
                "start_time": "09:00:00",
                "end_time": "12:00:00",
                "room_id": client_db["room"].id,
            },
            "violation_type": "MOBILE_PHONE",
            "description": "Manual filing create.",
            "recovered_materials": ["MOBILE_PHONE"],
            "signer_name": "Inv C15",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["student_roll"] == "C15-NEW-01"
    assert body["exam_course_code"] == "C15NEW"

    after_students = client_db["db"].scalar(select(func.count()).select_from(Student))
    after_exams = client_db["db"].scalar(select(func.count()).select_from(Exam))
    assert after_students == before_students + 1
    assert after_exams == before_exams + 1


def test_manual_student_reuses_existing_roll(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    before = client_db["db"].scalar(select(func.count()).select_from(Student))
    r = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "manual_student": {
                "student_id": "C15-ROLL-99",
                "name": "Different Name Ignored",
                "department": "CS",
                "program": "BSCS",
            },
            "exam_id": client_db["exam"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "Reuse existing roll.",
            "recovered_materials": ["MOBILE_PHONE"],
            "signer_name": "Inv C15",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["student_id"] == client_db["student"].id
    after = client_db["db"].scalar(select(func.count()).select_from(Student))
    assert after == before


def test_non_invigilators_cannot_create_ufm_case(client_db):
    c = client_db["client"]
    payload = {
        "student_id": client_db["student"].id,
        "exam_id": client_db["exam"].id,
        "violation_type": "MOBILE_PHONE",
        "description": "Should fail",
        "recovered_materials": ["MOBILE_PHONE"],
        "signer_name": "Someone",
        "signature_ack": True,
    }
    for role_key in ("hod", "dec", "exam_dept", "ufm", "student_user", "admin"):
        user = client_db[role_key]
        r = c.post("/ufm-cases", headers=_h(client_db["token"](user)), json=payload)
        assert r.status_code == 403, f"{role_key} got {r.status_code}"


def test_create_case_with_library_evidence_ids(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    orphan = client_db["orphan"]
    r = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "Library evidence attach test.",
            "recovered_materials": ["MOBILE_PHONE"],
            "signer_name": "Inv C15",
            "signature_ack": True,
            "evidence_ids": [orphan.id],
        },
    )
    assert r.status_code == 201, r.text
    case_id = r.json()["id"]
    client_db["db"].refresh(orphan)
    assert orphan.case_id == case_id

    listed = c.get(f"/evidence?case_id={case_id}", headers=h)
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()}
    assert orphan.id in ids


def test_cannot_attach_already_linked_evidence(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    owned = client_db["owned"]
    r = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "Attempt attach owned evidence.",
            "recovered_materials": ["MOBILE_PHONE"],
            "signer_name": "Inv C15",
            "signature_ack": True,
            "evidence_ids": [owned.id],
        },
    )
    assert r.status_code == 400
    assert "already linked" in r.text.lower()


def test_student_cannot_list_unlinked_library(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["student_user"]))
    r = c.get("/evidence?unlinked_only=true", headers=h)
    assert r.status_code == 200
    # Students only see own case evidence; unlinked orphans are not theirs.
    assert r.json() == [] or all(row.get("case_id") is not None for row in r.json())


def test_evidence_unlinked_only_list(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.get("/evidence?unlinked_only=true", headers=h)
    assert r.status_code == 200
    assert all(row["case_id"] is None for row in r.json())
    assert any(row["id"] == client_db["orphan"].id for row in r.json())
    assert all(row["id"] != client_db["owned"].id for row in r.json())


def test_create_case_page_wires_c15_components():
    if not CREATE_CASE_PAGE.is_file():
        pytest.skip("Frontend sources not mounted in this test environment")
    text = CREATE_CASE_PAGE.read_text(encoding="utf-8")
    assert "PortalSearchSelect" in text
    assert "FormModeToggle" not in text
    assert "EvidenceLibraryPicker" in text
    assert "Attach from Evidence Library" in text
    assert "manual_student" in text
    assert "manual_exam" in text
    assert "createStudent" not in text
    assert "createExam" not in text
    assert "onExamFieldChange" in text
    assert "onStaffFieldChange" in text
