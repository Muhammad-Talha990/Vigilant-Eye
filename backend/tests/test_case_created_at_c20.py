"""
C20 — case creation timestamp must be server system time.

  pytest -q tests/test_case_created_at_c20.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

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
from models.student import Student
from models.ufm_case import UfmCase
from models.user import User
from schemas.ufm_case import UfmCaseCreate
from security import create_access_token, hash_password

FRONTEND_CASE_PRESENTATION = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "src"
    / "config"
    / "casePresentation.js"
)
FRONTEND_CREATE_CASE = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "src"
    / "pages"
    / "CreateCasePage.jsx"
)


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

    inv = User(
        name="C20 Invigilator",
        email="c20-inv@test.local",
        password_hash=hash_password("Demo@12345"),
        role="INVIGILATOR",
        is_active=True,
    )
    db.add(inv)
    db.flush()

    room = ExamRoom(room_number="C20-R1", building="Block A", capacity=40)
    db.add(room)
    db.flush()

    student = Student(
        student_id="C20-ROLL-01",
        name="C20 Student",
        department="CS",
        program="BSCS",
    )
    exam = Exam(
        course_code="C20EX",
        course_name="C20 Exam",
        semester="Fall",
        exam_date=datetime(2026, 10, 3).date(),
        start_time=datetime(2026, 10, 3, 9, 0).time(),
        end_time=datetime(2026, 10, 3, 12, 0).time(),
        room_id=room.id,
    )
    db.add_all([student, exam])
    db.commit()
    db.refresh(inv)
    db.refresh(student)
    db.refresh(exam)

    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)

    def token(user: User) -> str:
        return create_access_token(
            user_id=user.id, email=user.email, role=user.role
        )

    yield {
        "client": client,
        "db": db,
        "inv": inv,
        "student": student,
        "exam": exam,
        "token": token,
    }

    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_created_at_is_server_time_within_create_window(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))

    before = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    r = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "C20 created_at window check.",
            "recovered_materials": ["MOBILE_PHONE"],
            "signer_name": "C20 Invigilator",
            "signature_ack": True,
        },
    )
    after = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=1)

    assert r.status_code == 201, r.text
    body = r.json()
    assert "created_at" in body and body["created_at"]

    created = datetime.fromisoformat(body["created_at"].replace("Z", ""))
    assert before <= created <= after

    row = client_db["db"].scalar(
        select(UfmCase).where(UfmCase.id == body["id"])
    )
    assert row is not None
    assert row.created_at is not None
    assert before <= row.created_at <= after

    # API and DB agree (to the second).
    assert abs((row.created_at - created).total_seconds()) < 1


def test_client_cannot_override_created_at(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    fake = "2001-01-01T00:00:00"

    before = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    r = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "C20 ignore client created_at.",
            "recovered_materials": ["MOBILE_PHONE"],
            "signer_name": "C20 Invigilator",
            "signature_ack": True,
            "created_at": fake,
            "updated_at": fake,
        },
    )
    after = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=1)

    assert r.status_code == 201, r.text
    body = r.json()
    created = datetime.fromisoformat(body["created_at"].replace("Z", ""))
    assert before <= created <= after
    assert not str(body["created_at"]).startswith("2001")

    # Schema still rejects using created_at as a real create field.
    fields = set(UfmCaseCreate.model_fields.keys())
    assert "created_at" not in fields
    assert "updated_at" not in fields


def test_frontend_does_not_use_live_clock_for_case_creation():
    if not FRONTEND_CREATE_CASE.is_file():
        pytest.skip("Frontend sources not mounted")
    text = FRONTEND_CREATE_CASE.read_text(encoding="utf-8")
    assert "Report timestamp: {new Date().toLocaleString()}" not in text
    assert "recorded by the server when you submit" in text

    if FRONTEND_CASE_PRESENTATION.is_file():
        helper = FRONTEND_CASE_PRESENTATION.read_text(encoding="utf-8")
        assert "formatCaseCreatedAt" in helper
