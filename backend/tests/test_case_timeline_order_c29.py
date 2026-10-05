"""
C29 — Case timeline: workflow action before resulting status.

Root cause previously: create_case_review set case.updated_at before
review.created_at (default-on-flush), so "Current status" sorted before Forward.

Run from backend/:
  pytest -q tests/test_case_timeline_order_c29.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend"
CASE_PRESENTATION = FE / "src" / "config" / "casePresentation.js"


def _index_action(events: list[dict], action: str, role: str) -> int:
    """Find timeline row by action/role labels (encoding-safe; ignores separator)."""
    action_l = action.lower()
    role_l = role.lower()
    for i, ev in enumerate(events):
        title = str(ev.get("title") or "").lower()
        if ev.get("kind") == "review" and action_l in title and role_l in title:
            return i
    raise AssertionError(f"missing review action {action!r} / {role!r} in {[e.get('title') for e in events]}")


def _index_current_status(events: list[dict], status_substr: str | None = None) -> int:
    for i, ev in enumerate(events):
        title = str(ev.get("title") or "")
        if ev.get("kind") == "status" and title.startswith("Current status:"):
            if status_substr is None or status_substr.lower() in title.lower():
                return i
    raise AssertionError(f"missing current status in {[e.get('title') for e in events]}")


def _sign(action: str, remarks: str = "ok") -> dict:
    return {
        "action": action,
        "remarks": remarks,
        "signer_name": "Timeline Tester",
        "signature_ack": True,
    }


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _eval_timeline(payload: dict) -> list[dict]:
    """Execute buildCaseTimeline via Node against the real module."""
    if shutil.which("node") is None:
        pytest.skip("node is required for casePresentation.js evaluation")
    body = json.dumps(payload)
    script = f"""
import {{ buildCaseTimeline }} from './src/config/casePresentation.js';
const input = {body};
const events = buildCaseTimeline(input);
process.stdout.write(JSON.stringify(events.map((e) => ({{
  id: e.id,
  kind: e.kind,
  title: e.title,
  at: e.at,
  sortAt: e.sortAt ?? null,
  current: Boolean(e.current),
}}))));
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


@pytest.fixture()
def client_db():
    # Lazy imports so Node-only timeline tests can run on hosts without cv2.
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

    room = ExamRoom(room_number="C29-R1", building="Block A", capacity=40)
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

    inv = add_user(email="inv.c29@demo.com", role="INVIGILATOR")
    hod = add_user(email="hod.c29@demo.com", role="HOD")
    dec = add_user(email="dec.c29@demo.com", role="DEC")
    exam = add_user(email="exam.c29@demo.com", role="EXAM_DEPARTMENT")
    ufm = add_user(email="ufm.c29@demo.com", role="UFM_COMMITTEE")

    student = Student(
        student_id="C29STU01",
        name="C29 Student",
        department="CS",
        program="BSCS",
    )
    exam_row = Exam(
        course_code="C29101",
        course_name="C29 Exam",
        semester="Fall",
        exam_date=date(2026, 10, 3),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    db.add_all([student, exam_row])
    db.commit()
    db.refresh(student)
    db.refresh(exam_row)

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
        "exam": exam,
        "ufm": ufm,
        "student": student,
        "exam_row": exam_row,
    }
    app.dependency_overrides.clear()
    db.close()


def _create_case(client_db) -> dict:
    c = client_db["client"]
    r = c.post(
        "/ufm-cases",
        headers=_h(client_db["token"](client_db["inv"])),
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam_row"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "C29 timeline case",
            "signer_name": "Inv C29",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_frontend_timeline_exports_ordering_helpers():
    text = CASE_PRESENTATION.read_text(encoding="utf-8")
    assert "TIMELINE_KIND_ORDER" in text
    assert "compareTimelineEvents" in text
    assert "buildCaseTimeline" in text
    assert text.index("review:") < text.index("status:")


def test_forward_and_status_same_timestamp_forward_appears_first():
    """Regression: equal transition timestamps → Forward before Current status."""
    ts = "2026-10-03T16:38:57.000Z"
    events = _eval_timeline(
        {
            "caseData": {
                "id": 9,
                "status": "EXAM_DEPARTMENT_REVIEW",
                "created_at": "2026-10-03T16:00:00.000Z",
                "updated_at": ts,
                "reporter_name": "Inv",
                "reporter_role": "INVIGILATOR",
            },
            "reviews": [
                {
                    "id": 1,
                    "action": "FORWARD",
                    "reviewer_role": "HOD",
                    "created_at": "2026-10-03T16:32:12.000Z",
                    "signed_at": "2026-10-03T16:32:12.000Z",
                    "remarks": "to DEC",
                },
                {
                    "id": 2,
                    "action": "FORWARD",
                    "reviewer_role": "DEC",
                    "created_at": ts,
                    "signed_at": ts,
                    "remarks": "to Exam",
                },
            ],
            "evidence": [],
            "clarifications": [],
            "includeEvidence": False,
            "includeClarifications": False,
        }
    )
    hod_i = _index_action(events, "Forward", "HOD")
    dec_i = _index_action(events, "Forward", "DEC")
    status_i = _index_current_status(events, "Exam Department Review")
    assert hod_i < dec_i < status_i
    assert events[status_i]["at"] == ts
    assert events[dec_i]["at"] == ts
    assert events[dec_i]["kind"] == "review"
    assert events[status_i]["kind"] == "status"


def test_historical_status_before_review_ms_still_orders_action_first():
    """Legacy rows: updated_at slightly earlier than review.created_at."""
    review_ts = "2026-10-03T16:38:57.120Z"
    status_ts = "2026-10-03T16:38:57.050Z"
    events = _eval_timeline(
        {
            "caseData": {
                "id": 11,
                "status": "EXAM_DEPARTMENT_REVIEW",
                "created_at": "2026-10-03T16:00:00.000Z",
                "updated_at": status_ts,
            },
            "reviews": [
                {
                    "id": 7,
                    "action": "FORWARD",
                    "reviewer_role": "DEC",
                    "created_at": review_ts,
                    "signed_at": review_ts,
                }
            ],
            "includeEvidence": False,
            "includeClarifications": False,
            "includeCreateSignOff": False,
            "includeReporterDetail": False,
            "includeResponsibleDetail": False,
        }
    )
    dec_i = _index_action(events, "Forward", "DEC")
    status_i = _index_current_status(events)
    assert dec_i < status_i
    # Displayed status timestamp remains the real case.updated_at
    assert events[status_i]["at"] == status_ts


def test_review_transition_shares_timestamp_with_case_updated_at(client_db):
    """Backend event model: one transition_at for review + resulting status."""
    from sqlalchemy import select

    from models.case_review import CaseReview
    from models.ufm_case import UfmCase

    case = _create_case(client_db)
    case_id = case["id"]
    c = client_db["client"]

    # HOD open may move PENDING → UNDER_REVIEW
    r = c.get(
        f"/ufm-cases/{case_id}",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r.status_code == 200

    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["hod"])),
        json=_sign("FORWARD", "to DEC"),
    )
    assert r.status_code == 201
    review = r.json()

    r = c.get(
        f"/ufm-cases/{case_id}",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r.status_code == 200
    case_body = r.json()
    assert case_body["status"] == "DEC_REVIEW"
    assert review["created_at"] == case_body["updated_at"]
    assert review["signed_at"] == case_body["updated_at"]

    db = client_db["db"]
    db.expire_all()
    row = db.scalar(select(CaseReview).where(CaseReview.case_id == case_id))
    ufm = db.get(UfmCase, case_id)
    assert row is not None and ufm is not None
    assert row.created_at == ufm.updated_at == row.signed_at


def test_full_chain_timeline_actions_before_current_status():
    """PENDING→HOD→DEC→Exam→UFM→APPROVED reads action then resulting status."""
    t0 = datetime(2026, 10, 3, 16, 0, 0)
    steps = [
        ("HOD", "FORWARD", t0 + timedelta(minutes=10)),
        ("DEC", "FORWARD", t0 + timedelta(minutes=20)),
        ("EXAM_DEPARTMENT", "FORWARD", t0 + timedelta(minutes=30)),
        ("UFM_COMMITTEE", "APPROVE", t0 + timedelta(minutes=40)),
    ]
    reviews = []
    for i, (role, action, at) in enumerate(steps, start=1):
        iso = at.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        reviews.append(
            {
                "id": i,
                "action": action,
                "reviewer_role": role,
                "created_at": iso,
                "signed_at": iso,
            }
        )
    final_ts = steps[-1][2].strftime("%Y-%m-%dT%H:%M:%S.000Z")
    events = _eval_timeline(
        {
            "caseData": {
                "id": 42,
                "status": "APPROVED",
                "created_at": t0.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                "updated_at": final_ts,
            },
            "reviews": reviews,
            "includeEvidence": False,
            "includeClarifications": False,
            "includeCreateSignOff": False,
        }
    )
    hod_i = _index_action(events, "Forward", "HOD")
    dec_i = _index_action(events, "Forward", "DEC")
    exam_i = _index_action(events, "Forward", "Exam Department")
    approve_i = _index_action(events, "Approve", "UFM Committee")
    status_i = _index_current_status(events, "Approved")
    assert hod_i < dec_i < exam_i < approve_i < status_i


def test_return_to_pending_timeline_order():
    ts = "2026-10-03T17:00:00.000Z"
    events = _eval_timeline(
        {
            "caseData": {
                "id": 5,
                "status": "PENDING",
                "created_at": "2026-10-03T16:00:00.000Z",
                "updated_at": ts,
            },
            "reviews": [
                {
                    "id": 1,
                    "action": "FORWARD",
                    "reviewer_role": "HOD",
                    "created_at": "2026-10-03T16:30:00.000Z",
                },
                {
                    "id": 2,
                    "action": "RETURN",
                    "reviewer_role": "DEC",
                    "created_at": ts,
                    "signed_at": ts,
                },
            ],
            "includeEvidence": False,
            "includeClarifications": False,
            "includeCreateSignOff": False,
        }
    )
    assert _index_action(events, "Return", "DEC") < _index_current_status(
        events, "Pending"
    )
