"""
Minimal API smoke tests (SQLite in-memory via dependency override).

Run from backend/:
  pytest -q
"""

from __future__ import annotations

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
from security import hash_password


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        invig = User(
            name="Invig Demo",
            email="invigilator@demo.com",
            password_hash=hash_password("Demo@123"),
            role="INVIGILATOR",
            is_active=True,
        )
        db.add(invig)
        db.flush()
        room = ExamRoom(room_number="A-101", building="Block A", capacity=40)
        db.add(room)
        db.flush()
        student = Student(
            student_id="DEMO001",
            name="Demo Student",
            department="CS",
            program="BS",
        )
        db.add(student)
        exam = Exam(
            course_code="CS101",
            course_name="Intro",
            semester="Fall",
            exam_date=__import__("datetime").date(2026, 1, 15),
            start_time=__import__("datetime").time(9, 0),
            end_time=__import__("datetime").time(12, 0),
            room_id=room.id,
        )
        db.add(exam)
        db.commit()
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
        yield c
    app.dependency_overrides.clear()


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_and_list_cases(client: TestClient):
    login = client.post(
        "/auth/login",
        json={"email": "invigilator@demo.com", "password": "Demo@123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    cases = client.get("/ufm-cases", headers=headers)
    assert cases.status_code == 200
    assert isinstance(cases.json(), list)


def test_create_case_with_signoff(client: TestClient):
    login = client.post(
        "/auth/login",
        json={"email": "invigilator@demo.com", "password": "Demo@123"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    students = client.get("/students", headers=headers)
    exams = client.get("/exams", headers=headers)
    assert students.status_code == 200
    assert exams.status_code == 200
    student_id = students.json()[0]["id"]
    exam_id = exams.json()[0]["id"]

    created = client.post(
        "/ufm-cases",
        headers=headers,
        json={
            "student_id": student_id,
            "exam_id": exam_id,
            "violation_type": "MOBILE_PHONE",
            "description": "Phone visible during exam (smoke test).",
            "remarks": None,
            "signer_name": "Invig Demo",
            "signature_ack": True,
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["case_number"].startswith("UFM-")
    assert body["student_roll"] == "DEMO001"
    assert body["signer_name"] == "Invig Demo"
    assert body["exam_course_code"] == "CS101"
