"""
Phase 11 — student isolation + monitoring authorization tests.

Run from backend/:
  pytest -q tests/test_authz_phase11.py
"""

from __future__ import annotations

from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models.base import Base
from models.camera import Camera
from models.detection import Detection
from models.exam import Exam
from models.exam_room import ExamRoom
from models.student import Student
from models.user import User
from security import hash_password


@pytest.fixture()
def client_db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        student = User(
            name="Student",
            email="student@demo.com",
            password_hash=hash_password("Demo@123"),
            role="STUDENT",
            is_active=True,
        )
        invig = User(
            name="Invig",
            email="invigilator@demo.com",
            password_hash=hash_password("Demo@123"),
            role="INVIGILATOR",
            is_active=True,
        )
        hod = User(
            name="HOD",
            email="hod@demo.com",
            password_hash=hash_password("Demo@123"),
            role="HOD",
            is_active=True,
        )
        dec = User(
            name="DEC",
            email="dec@demo.com",
            password_hash=hash_password("Demo@123"),
            role="DEC",
            is_active=True,
        )
        ufm = User(
            name="UFM",
            email="ufm@demo.com",
            password_hash=hash_password("Demo@123"),
            role="UFM_COMMITTEE",
            is_active=True,
        )
        db.add_all([student, invig, hod, dec, ufm])
        db.flush()

        room = ExamRoom(room_number="A-101", building="Block A", capacity=40)
        db.add(room)
        db.flush()
        db.add(
            Student(
                student_id="STU1",
                name="Student One",
                department="CS",
                program="BS",
                user_id=student.id,
            )
        )
        db.add(
            Exam(
                course_code="CS101",
                course_name="Intro",
                semester="Fall",
                exam_date=date(2026, 1, 15),
                start_time=time(9, 0),
                end_time=time(12, 0),
                room_id=room.id,
            )
        )
        cam = Camera(
            camera_id="CAM-1",
            name="Hall Cam",
            room_id=room.id,
            stream_url="webcam:0",
            is_active=True,
        )
        db.add(cam)
        det = Detection(
            camera_id=None,
            detection_type="phone",
            confidence=0.9,
            is_confirmed=True,
            is_seen=False,
            is_demo=False,
        )
        db.add(det)
        db.commit()
        det_id = det.id
        cam_id = cam.id
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
        yield c, TestingSessionLocal, det_id, cam_id
    app.dependency_overrides.clear()


def _headers(client: TestClient, email: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": "Demo@123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_student_denied_detections_and_mark_seen(client_db):
    client, SessionLocal, det_id, _cam_id = client_db
    h = _headers(client, "student@demo.com")

    assert client.get("/detections", headers=h).status_code == 403
    assert (
        client.patch(f"/detections/{det_id}/seen", headers=h).status_code == 403
    )
    assert client.post("/detections/mark-all-seen", headers=h).status_code == 403

    # No mutation after denied mark-all-seen
    db = SessionLocal()
    try:
        row = db.get(Detection, det_id)
        assert row is not None
        assert row.is_seen is False
    finally:
        db.close()


def test_invigilator_detections_and_mark_seen(client_db):
    client, SessionLocal, det_id, _cam_id = client_db
    h = _headers(client, "invigilator@demo.com")

    listed = client.get("/detections", headers=h)
    assert listed.status_code == 200
    assert any(d["id"] == det_id for d in listed.json())

    marked = client.patch(f"/detections/{det_id}/seen", headers=h)
    assert marked.status_code == 200
    assert marked.json()["is_seen"] is True

    db = SessionLocal()
    try:
        # Reset for mark-all-seen
        row = db.get(Detection, det_id)
        row.is_seen = False
        db.commit()
    finally:
        db.close()

    all_seen = client.post("/detections/mark-all-seen", headers=h)
    assert all_seen.status_code == 200
    assert all_seen.json()["updated"] >= 1

    db = SessionLocal()
    try:
        assert db.get(Detection, det_id).is_seen is True
    finally:
        db.close()


def test_student_denied_cameras_students_exams_rooms(client_db):
    client, _SessionLocal, _det_id, _cam_id = client_db
    h = _headers(client, "student@demo.com")
    assert client.get("/cameras", headers=h).status_code == 403
    assert client.get("/students", headers=h).status_code == 403
    assert client.get("/exams", headers=h).status_code == 403
    assert client.get("/exam-rooms", headers=h).status_code == 403


def test_staff_allowed_cameras_students_exams_rooms(client_db):
    client, _SessionLocal, _det_id, _cam_id = client_db
    inv = _headers(client, "invigilator@demo.com")
    assert client.get("/cameras", headers=inv).status_code == 200
    assert client.get("/students", headers=inv).status_code == 200
    assert client.get("/exams", headers=inv).status_code == 200
    assert client.get("/exam-rooms", headers=inv).status_code == 200

    # UFM may list students but not detections / camera / exam catalogs (C11-B)
    ufm = _headers(client, "ufm@demo.com")
    assert client.get("/students", headers=ufm).status_code == 200
    assert client.get("/detections", headers=ufm).status_code == 403
    assert client.get("/cameras", headers=ufm).status_code == 403
    assert client.get("/exams", headers=ufm).status_code == 403

    # DEC: cameras OK for context; detections denied (C11-B)
    dec = _headers(client, "dec@demo.com")
    assert client.get("/cameras", headers=dec).status_code == 200
    assert client.get("/detections", headers=dec).status_code == 403
    assert client.get("/live/status", headers=dec).status_code == 403


def test_student_denied_live_status_and_streams(client_db):
    client, _SessionLocal, _det_id, cam_id = client_db
    h = _headers(client, "student@demo.com")

    assert client.get("/live/status", headers=h).status_code == 403
    assert (
        client.get(f"/live/cameras/{cam_id}/snapshot", headers=h).status_code
        == 403
    )
    assert (
        client.get(f"/live/cameras/{cam_id}/mjpeg", headers=h).status_code == 403
    )


def test_monitor_role_live_status_allowed(client_db):
    client, _SessionLocal, _det_id, cam_id = client_db
    h = _headers(client, "invigilator@demo.com")
    status_r = client.get("/live/status", headers=h)
    assert status_r.status_code == 200
    body = status_r.json()
    assert "sessions" in body or "active_sessions" in body

    # No active session → 404 after auth (auth checked first; not 403)
    snap = client.get(f"/live/cameras/{cam_id}/snapshot", headers=h)
    assert snap.status_code in (404, 503)


def test_dec_denied_live_status_matches_monitor_policy(client_db):
    """DEC is not in MONITOR_ROLES (cannot start live); status/stream denied."""
    client, _SessionLocal, _det_id, cam_id = client_db
    h = _headers(client, "dec@demo.com")
    assert client.get("/live/status", headers=h).status_code == 403
    assert (
        client.get(f"/live/cameras/{cam_id}/snapshot", headers=h).status_code
        == 403
    )
    # DEC may still list cameras (monitoring page registry)
    assert client.get("/cameras", headers=h).status_code == 200
