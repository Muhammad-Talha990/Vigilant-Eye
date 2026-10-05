"""Phase C6 — UFM cases CSV export completeness."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models.base import Base
from models.camera import Camera
from models.exam import Exam
from models.exam_room import ExamRoom
from models.student import Student
from models.ufm_case import UfmCase
from models.user import User
from schemas.ufm_case import serialize_recovered_materials
from security import create_access_token, hash_password

LEGACY_COLUMNS = [
    "id",
    "case_number",
    "status",
    "violation_type",
    "student_roll",
    "student_name",
    "student_department",
    "exam_course_code",
    "exam_course_name",
    "exam_date",
    "room_number",
    "reporter_name",
    "signer_name",
    "signed_at",
    "created_at",
]

NEW_COLUMNS = [
    "recovered_materials",
    "recovered_other_detail",
    "description",
    "remarks",
    "exam_semester",
    "updated_at",
    "camera_id",
    "camera_code",
    "camera_name",
]


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

    room = ExamRoom(room_number="CSV-R1", building="Block A", capacity=40)
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

    inv = add_user(email="invig.csv.export@demo.com", role="INVIGILATOR", name="Invig CSV")
    hod = add_user(email="hod.csv.export@demo.com", role="HOD", name="Hod CSV")
    student_user = add_user(
        email="student.csv.export@demo.com", role="STUDENT", name="Student CSV"
    )
    admin = add_user(
        email="admin.csv.export@demo.com", role="ADMINISTRATOR", name="Admin CSV"
    )

    student = Student(
        student_id="CSVEXP01",
        name="CSV Export Student",
        department="CS",
        program="BSCS",
        user_id=student_user.id,
    )
    exam = Exam(
        course_code="CSV101",
        course_name="CSV Export Exam",
        semester="Spring 2026",
        exam_date=date(2026, 3, 15),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    cam = Camera(
        camera_id="CAM-CSV-01",
        name="CSV Room Cam",
        room_id=room.id,
        stream_url="rtsp://demo/csv",
        is_active=True,
    )
    db.add_all([student, exam, cam])
    db.commit()
    db.refresh(student)
    db.refresh(exam)
    db.refresh(cam)

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
        "admin": admin,
        "student_user": student_user,
        "student": student,
        "exam": exam,
        "cam": cam,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _parse_csv(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def _seed_case(ctx, *, camera_id=None, description=None, remarks=None):
    db = ctx["db"]
    case = UfmCase(
        case_number="UFM-CSV-001",
        student_id=ctx["student"].id,
        exam_id=ctx["exam"].id,
        reported_by=ctx["inv"].id,
        violation_type="MOBILE_PHONE",
        description=description
        or 'Phone found under desk, "confiscated",\nand logged.',
        remarks=remarks or "See annex A, B",
        recovered_materials=serialize_recovered_materials(
            ["MOBILE_PHONE", "ANSWER_EXTRA_SHEET"]
        ),
        recovered_other_detail=None,
        status="PENDING",
        camera_id=camera_id,
        signer_name="Invig CSV",
        signature_ack=True,
        signed_at=datetime(2026, 3, 15, 10, 30, 0),
        created_at=datetime(2026, 3, 15, 10, 30, 0),
        updated_at=datetime(2026, 3, 15, 11, 0, 0),
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def test_export_preserves_legacy_and_adds_new_columns(client_db):
    _seed_case(client_db, camera_id=client_db["cam"].id)
    c = client_db["client"]
    h = _h(client_db["token"](client_db["hod"]))

    r = c.get("/ufm-cases/export.csv", headers=h)
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers.get("content-type", "")
    assert "ufm_cases.csv" in r.headers.get("content-disposition", "")

    reader = csv.reader(io.StringIO(r.text))
    header = next(reader)
    for col in LEGACY_COLUMNS:
        assert col in header, f"missing legacy column {col}"
    for col in NEW_COLUMNS:
        assert col in header, f"missing new column {col}"
    # Legacy columns keep their relative order at the start
    assert header[: len(LEGACY_COLUMNS)] == LEGACY_COLUMNS


def test_export_values_match_authoritative_case_data(client_db):
    case = _seed_case(client_db, camera_id=client_db["cam"].id)
    c = client_db["client"]
    h = _h(client_db["token"](client_db["hod"]))

    r = c.get("/ufm-cases/export.csv", headers=h)
    assert r.status_code == 200
    rows = _parse_csv(r.text)
    assert len(rows) == 1
    row = rows[0]

    assert row["id"] == str(case.id)
    assert row["case_number"] == case.case_number
    assert row["status"] == "PENDING"
    assert row["violation_type"] == "MOBILE_PHONE"
    assert row["student_roll"] == "CSVEXP01"
    assert row["student_name"] == "CSV Export Student"
    assert row["exam_course_code"] == "CSV101"
    assert row["exam_semester"] == "Spring 2026"
    assert row["description"] == case.description
    assert row["remarks"] == case.remarks
    assert json.loads(row["recovered_materials"]) == [
        "MOBILE_PHONE",
        "ANSWER_EXTRA_SHEET",
    ]
    assert row["recovered_other_detail"] == ""
    assert row["camera_id"] == str(client_db["cam"].id)
    assert row["camera_code"] == "CAM-CSV-01"
    assert row["camera_name"] == "CSV Room Cam"
    assert "2026-03-15" in row["updated_at"]
    assert "password" not in r.text.lower()
    assert "token" not in {k.lower() for k in row.keys()}
    assert "password_hash" not in r.text.lower()


def test_historical_null_camera_exports_blank(client_db):
    _seed_case(client_db, camera_id=None)
    c = client_db["client"]
    h = _h(client_db["token"](client_db["hod"]))
    r = c.get("/ufm-cases/export.csv", headers=h)
    assert r.status_code == 200
    row = _parse_csv(r.text)[0]
    assert row["camera_id"] == ""
    assert row["camera_code"] == ""
    assert row["camera_name"] == ""


def test_csv_escaping_commas_quotes_newlines(client_db):
    tricky = 'Line1, "quoted",\nand more'
    _seed_case(
        client_db,
        camera_id=None,
        description=tricky,
        remarks='Note: "urgent", please review',
    )
    c = client_db["client"]
    h = _h(client_db["token"](client_db["hod"]))
    r = c.get("/ufm-cases/export.csv", headers=h)
    assert r.status_code == 200
    rows = _parse_csv(r.text)
    assert len(rows) == 1
    assert rows[0]["description"] == tricky
    assert rows[0]["remarks"] == 'Note: "urgent", please review'


def test_export_includes_all_cases_in_order(client_db):
    """Export has no query filters today — all cases, latest-first (created_at DESC, id DESC)."""
    db = client_db["db"]
    _seed_case(client_db, camera_id=None)
    second = UfmCase(
        case_number="UFM-CSV-002",
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        violation_type="OTHER",
        description="Second case",
        status="UNDER_REVIEW",
        signer_name="Invig CSV",
        signature_ack=True,
    )
    db.add(second)
    db.commit()
    db.refresh(second)

    c = client_db["client"]
    h = _h(client_db["token"](client_db["hod"]))
    r = c.get("/ufm-cases/export.csv", headers=h)
    assert r.status_code == 200
    rows = _parse_csv(r.text)
    assert [row["case_number"] for row in rows] == ["UFM-CSV-002", "UFM-CSV-001"]


def test_invigilator_can_export_own_cases_csv(client_db):
    """C27: Invigilator may export CSV scoped to cases they reported."""
    _seed_case(client_db)
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.get("/ufm-cases/export.csv", headers=h)
    assert r.status_code == 200, r.text
    rows = _parse_csv(r.text)
    assert len(rows) >= 1
    assert all(row.get("case_number") for row in rows)


def test_student_cannot_export_csv(client_db):
    _seed_case(client_db)
    c = client_db["client"]
    h = _h(client_db["token"](client_db["student_user"]))
    r = c.get("/ufm-cases/export.csv", headers=h)
    assert r.status_code == 403


def test_administrator_cannot_export_csv(client_db):
    _seed_case(client_db)
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    r = c.get("/ufm-cases/export.csv", headers=h)
    assert r.status_code == 403


def test_unauthenticated_cannot_export_csv(client_db):
    r = client_db["client"].get("/ufm-cases/export.csv")
    assert r.status_code in (401, 403)
