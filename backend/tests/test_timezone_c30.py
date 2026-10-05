"""
C30 — UTC storage / API Z serialization / Asia/Karachi display contract.

Run from backend/:
  pytest -q tests/test_timezone_c30.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date, datetime, time, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from time_utils import to_api_iso, utc_now

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"
DATE_TIME_JS = FE / "src" / "config" / "dateTime.js"
CASE_PRESENTATION = FE / "src" / "config" / "casePresentation.js"


def test_utc_now_is_naive_utc_wall_clock():
    before = datetime.now(timezone.utc).replace(tzinfo=None)
    now = utc_now()
    after = datetime.now(timezone.utc).replace(tzinfo=None)
    assert now.tzinfo is None
    assert before <= now <= after


def test_to_api_iso_appends_z_for_naive_utc():
    dt = datetime(2026, 10, 4, 10, 18, 31)
    assert to_api_iso(dt) == "2026-10-04T10:18:31Z"
    assert to_api_iso(None) is None
    aware = datetime(2026, 10, 4, 10, 18, 31, tzinfo=timezone.utc)
    assert to_api_iso(aware) == "2026-10-04T10:18:31Z"


def _eval_format(cases: list[dict]) -> list[str]:
    if shutil.which("node") is None:
        pytest.skip("node required for dateTime.js evaluation")
    payload = json.dumps(cases)
    script = f"""
import {{ formatDateTime, parseApiDateTime, DISPLAY_TIMEZONE }} from './src/config/dateTime.js';
const cases = {payload};
const out = cases.map((c) => formatDateTime(c.value));
if (DISPLAY_TIMEZONE !== 'Asia/Karachi') throw new Error('tz');
process.stdout.write(JSON.stringify(out));
"""
    proc = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=str(FE),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout or "node failed")
    return json.loads(proc.stdout)


def test_frontend_karachi_display_known_utc_instant():
    """2026-10-04T10:18:31Z → 04/10/2026, 15:18:31 Asia/Karachi."""
    out = _eval_format([{"value": "2026-10-04T10:18:31Z"}])
    assert out == ["04/10/2026, 15:18:31"]


def test_frontend_karachi_date_rollover():
    """2026-10-04T19:30:00Z → 05/10/2026, 00:30:00 Asia/Karachi."""
    out = _eval_format([{"value": "2026-10-04T19:30:00Z"}])
    assert out == ["05/10/2026, 00:30:00"]


def test_frontend_naive_iso_treated_as_utc():
    out = _eval_format([{"value": "2026-10-04T10:18:31"}])
    assert out == ["04/10/2026, 15:18:31"]


def test_frontend_central_formatter_exists():
    text = DATE_TIME_JS.read_text(encoding="utf-8")
    assert 'DISPLAY_TIMEZONE = "Asia/Karachi"' in text
    assert "formatDateTime" in text
    assert "parseApiDateTime" in text
    cp = CASE_PRESENTATION.read_text(encoding="utf-8")
    assert "formatDateTime" in cp
    assert "apiDateTimeMs" in cp


@pytest.fixture()
def client_db():
    from database import get_db
    from main import app
    from models.base import Base
    from models.exam import Exam
    from models.exam_room import ExamRoom
    from models.student import Student
    from models.user import User
    from security import create_access_token, hash_password

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

    room = ExamRoom(room_number="C30-R1", building="A", capacity=40)
    db.add(room)
    db.commit()
    db.refresh(room)

    inv = User(
        name="C30 Inv",
        email="inv.c30@demo.com",
        password_hash=hash_password("UnusedPass1!"),
        role="INVIGILATOR",
        is_active=True,
    )
    hod = User(
        name="C30 Hod",
        email="hod.c30@demo.com",
        password_hash=hash_password("UnusedPass1!"),
        role="HOD",
        is_active=True,
    )
    db.add_all([inv, hod])
    db.commit()
    db.refresh(inv)
    db.refresh(hod)

    student = Student(
        student_id="C30STU01",
        name="C30 Student",
        department="CS",
        program="BSCS",
    )
    exam = Exam(
        course_code="C30101",
        course_name="C30 Exam",
        semester="Fall",
        exam_date=date(2026, 10, 4),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    db.add_all([student, exam])
    db.commit()
    db.refresh(student)
    db.refresh(exam)

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
        "student": student,
        "exam": exam,
    }
    app.dependency_overrides.clear()
    db.close()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_case_create_api_emits_z_utc(client_db):
    c = client_db["client"]
    r = c.post(
        "/ufm-cases",
        headers=_h(client_db["token"](client_db["inv"])),
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "C30 timezone case",
            "recovered_materials": ["MOBILE_PHONE"],
            "signer_name": "C30 Invigilator",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert str(body["created_at"]).endswith("Z")
    assert str(body["updated_at"]).endswith("Z")
    assert str(body["signed_at"]).endswith("Z")

    # Notification timestamps also carry Z
    from sqlalchemy import select

    from models.notification import Notification

    db = client_db["db"]
    db.expire_all()
    notes = db.scalars(
        select(Notification).order_by(Notification.id.desc()).limit(5)
    ).all()
    assert notes
    # Re-fetch via API as hod may see case notifications
    r2 = c.get(
        "/notifications",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r2.status_code == 200
    items = r2.json()
    assert isinstance(items, list)
    if items:
        assert str(items[0]["created_at"]).endswith("Z")


def test_review_transition_at_api_emits_z(client_db):
    c = client_db["client"]
    r = c.post(
        "/ufm-cases",
        headers=_h(client_db["token"](client_db["inv"])),
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "C30 review tz",
            "recovered_materials": ["MOBILE_PHONE"],
            "signer_name": "C30 Invigilator",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201
    case_id = r.json()["id"]
    c.get(f"/ufm-cases/{case_id}", headers=_h(client_db["token"](client_db["hod"])))
    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["hod"])),
        json={
            "action": "FORWARD",
            "remarks": "tz",
            "signer_name": "C30 HOD",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text
    review = r.json()
    assert str(review["created_at"]).endswith("Z")
    assert str(review["signed_at"]).endswith("Z")
    assert review["created_at"] == review["signed_at"]

    case = c.get(
        f"/ufm-cases/{case_id}",
        headers=_h(client_db["token"](client_db["hod"])),
    ).json()
    assert case["updated_at"] == review["created_at"]
