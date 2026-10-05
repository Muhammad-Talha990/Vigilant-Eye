"""Phase C5 — UFM case camera_id end-to-end metadata."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path

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

    room_a = ExamRoom(room_number="CAM-R1", building="Block A", capacity=40)
    room_b = ExamRoom(room_number="CAM-R2", building="Block B", capacity=40)
    db.add_all([room_a, room_b])
    db.commit()
    db.refresh(room_a)
    db.refresh(room_b)

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

    inv = add_user(email="invig.case.cam@demo.com", role="INVIGILATOR", name="Invig Cam")
    student_user = add_user(
        email="student.case.cam@demo.com", role="STUDENT", name="Student Cam"
    )
    admin = add_user(
        email="admin.case.cam@demo.com", role="ADMINISTRATOR", name="Admin Cam"
    )
    other_student_user = add_user(
        email="other.student.cam@demo.com", role="STUDENT", name="Other Student"
    )

    student = Student(
        student_id="CAMCASE01",
        name="Camera Case Student",
        department="CS",
        program="BSCS",
        user_id=student_user.id,
    )
    other_student = Student(
        student_id="CAMCASE02",
        name="Other Camera Student",
        department="CS",
        program="BSCS",
        user_id=other_student_user.id,
    )
    exam = Exam(
        course_code="CAM101",
        course_name="Camera Case Exam",
        semester="Fall",
        exam_date=date(2026, 6, 1),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room_a.id,
    )
    exam_b = Exam(
        course_code="CAM102",
        course_name="Other Room Exam",
        semester="Fall",
        exam_date=date(2026, 6, 2),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room_b.id,
    )
    cam_a = Camera(
        camera_id="CAM-A-01",
        name="Room A Front",
        room_id=room_a.id,
        stream_url="rtsp://demo/a",
        is_active=True,
    )
    cam_a_inactive = Camera(
        camera_id="CAM-A-INACTIVE",
        name="Room A Offline",
        room_id=room_a.id,
        stream_url="rtsp://demo/a-off",
        is_active=False,
    )
    cam_b = Camera(
        camera_id="CAM-B-01",
        name="Room B Front",
        room_id=room_b.id,
        stream_url="rtsp://demo/b",
        is_active=True,
    )
    db.add_all([student, other_student, exam, exam_b, cam_a, cam_a_inactive, cam_b])
    db.commit()
    for obj in (student, other_student, exam, exam_b, cam_a, cam_a_inactive, cam_b):
        db.refresh(obj)

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
        "admin": admin,
        "student_user": student_user,
        "other_student_user": other_student_user,
        "student": student,
        "other_student": other_student,
        "exam": exam,
        "exam_b": exam_b,
        "room_a": room_a,
        "room_b": room_b,
        "cam_a": cam_a,
        "cam_a_inactive": cam_a_inactive,
        "cam_b": cam_b,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _base_payload(ctx, **overrides):
    body = {
        "student_id": ctx["student"].id,
        "exam_id": ctx["exam"].id,
        "violation_type": "MOBILE_PHONE",
        "description": "Camera metadata test case.",
        "signer_name": "Invig Cam",
        "signature_ack": True,
    }
    body.update(overrides)
    return body


def test_create_case_with_valid_camera_id(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    cam = client_db["cam_a"]

    r = c.post(
        "/ufm-cases",
        headers=h,
        json=_base_payload(client_db, camera_id=cam.id),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["camera_id"] == cam.id
    assert body["camera_code"] == "CAM-A-01"
    assert body["camera_name"] == "Room A Front"

    listed = c.get("/ufm-cases", headers=h)
    assert listed.status_code == 200
    match = next(x for x in listed.json() if x["id"] == body["id"])
    assert match["camera_id"] == cam.id
    assert match["camera_code"] == "CAM-A-01"


def test_create_case_rejects_nonexistent_camera(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.post(
        "/ufm-cases",
        headers=h,
        json=_base_payload(client_db, camera_id=999999),
    )
    assert r.status_code == 400
    assert "Camera not found" in r.json()["detail"]


def test_create_case_rejects_camera_from_unrelated_room(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.post(
        "/ufm-cases",
        headers=h,
        json=_base_payload(client_db, camera_id=client_db["cam_b"].id),
    )
    assert r.status_code == 400
    assert "examination room" in r.json()["detail"].lower()


def test_create_case_rejects_inactive_camera_manual(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.post(
        "/ufm-cases",
        headers=h,
        json=_base_payload(client_db, camera_id=client_db["cam_a_inactive"].id),
    )
    assert r.status_code == 400
    assert "inactive" in r.json()["detail"].lower()


def test_detection_originated_case_gets_authoritative_camera(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    db = client_db["db"]
    cam = client_db["cam_a"]

    det = Detection(
        camera_id=cam.id,
        student_id=client_db["student"].id,
        detection_type="mobile_phone",
        confidence=0.91,
        timestamp=datetime.utcnow(),
        is_confirmed=True,
        is_seen=True,
        is_demo=False,
        frame_index=12,
    )
    db.add(det)
    db.commit()
    db.refresh(det)

    # Explicit forged camera_id must be ignored in favour of detection camera.
    r = c.post(
        "/ufm-cases",
        headers=h,
        json=_base_payload(
            client_db,
            detection_id=det.id,
            camera_id=client_db["cam_b"].id,
        ),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["camera_id"] == cam.id
    assert body["camera_code"] == cam.camera_id

    draft = c.post(
        f"/detections/{det.id}/create-draft-case",
        headers=h,
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
        },
    )
    # First create already linked evidence / may still allow draft depending on
    # idempotency — if 400 because detection reused, create a second detection.
    if draft.status_code == 201:
        assert draft.json()["camera_id"] == cam.id
    else:
        det2 = Detection(
            camera_id=cam.id,
            student_id=client_db["student"].id,
            detection_type="mobile_phone",
            confidence=0.88,
            timestamp=datetime.utcnow(),
            is_confirmed=True,
            is_seen=True,
            is_demo=False,
            frame_index=20,
        )
        db.add(det2)
        db.commit()
        db.refresh(det2)
        draft2 = c.post(
            f"/detections/{det2.id}/create-draft-case",
            headers=h,
            json={
                "student_id": client_db["student"].id,
                "exam_id": client_db["exam"].id,
            },
        )
        assert draft2.status_code == 201, draft2.text
        assert draft2.json()["camera_id"] == cam.id
        assert draft2.json()["camera_code"] == cam.camera_id


def test_historical_case_null_camera_remains_readable(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    db = client_db["db"]

    case = UfmCase(
        case_number="UFM-HIST-CAM-1",
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        violation_type="MOBILE_PHONE",
        description="Historical case without camera metadata.",
        status="PENDING",
        camera_id=None,
        signer_name="Invig Cam",
        signature_ack=True,
        signed_at=datetime.utcnow(),
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    got = c.get(f"/ufm-cases/{case.id}", headers=h)
    assert got.status_code == 200
    body = got.json()
    assert body["camera_id"] is None
    assert body["camera_code"] is None
    assert body["camera_name"] is None

    listed = c.get("/ufm-cases", headers=h)
    assert listed.status_code == 200
    match = next(x for x in listed.json() if x["id"] == case.id)
    assert match["camera_id"] is None


def test_create_without_camera_still_works(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.post("/ufm-cases", headers=h, json=_base_payload(client_db))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["camera_id"] is None
    assert body["status"] == "PENDING"


def test_student_cannot_inject_camera_on_create(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["student_user"]))
    r = c.post(
        "/ufm-cases",
        headers=h,
        json=_base_payload(client_db, camera_id=client_db["cam_a"].id),
    )
    assert r.status_code == 403


def test_administrator_cannot_create_case_with_camera(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    r = c.post(
        "/ufm-cases",
        headers=h,
        json=_base_payload(client_db, camera_id=client_db["cam_a"].id),
    )
    assert r.status_code == 403


def test_student_isolation_on_case_with_camera(client_db):
    c = client_db["client"]
    inv_h = _h(client_db["token"](client_db["inv"]))
    created = c.post(
        "/ufm-cases",
        headers=inv_h,
        json=_base_payload(client_db, camera_id=client_db["cam_a"].id),
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]

    owner_h = _h(client_db["token"](client_db["student_user"]))
    owner_got = c.get(f"/ufm-cases/{case_id}", headers=owner_h)
    assert owner_got.status_code == 200
    assert owner_got.json()["camera_code"] == "CAM-A-01"

    other_h = _h(client_db["token"](client_db["other_student_user"]))
    other_got = c.get(f"/ufm-cases/{case_id}", headers=other_h)
    assert other_got.status_code in (403, 404)


def test_detection_camera_wrong_exam_room_rejected(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    db = client_db["db"]

    det = Detection(
        camera_id=client_db["cam_b"].id,
        student_id=client_db["student"].id,
        detection_type="mobile_phone",
        confidence=0.9,
        timestamp=datetime.utcnow(),
        is_confirmed=True,
        is_seen=True,
        is_demo=False,
    )
    db.add(det)
    db.commit()
    db.refresh(det)

    r = c.post(
        "/ufm-cases",
        headers=h,
        json=_base_payload(client_db, detection_id=det.id),
    )
    assert r.status_code == 400
    assert "examination room" in r.json()["detail"].lower()


def test_alembic_head_includes_case_camera():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    # case_camera remains in the lineage; AI model_version is the current head.
    assert script.get_current_head() == "20261004_0006_detection_model_version"
    revs = {r.revision for r in script.walk_revisions()}
    assert "20260930_0004_ufm_form" in revs
    assert "20260930_0005_case_camera" in revs
    assert "20261004_0006_detection_model_version" in revs
    case_cam = script.get_revision("20260930_0005_case_camera")
    assert case_cam is not None
    # Ensure model_version descends from case_camera (single linear chain).
    head = script.get_revision("20261004_0006_detection_model_version")
    assert head.down_revision == "20260930_0005_case_camera"
