"""
C21 — case list latest-first + DEC dashboard label.

  pytest -q tests/test_case_sort_c21.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

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
from models.ufm_case import UfmCase
from models.user import User
from security import create_access_token, hash_password

ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_BY_ROLE = ROOT / "frontend" / "src" / "config" / "dashboardByRole.js"
NAV_BY_ROLE = ROOT / "frontend" / "src" / "config" / "navByRole.js"


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
        name="C21 Inv",
        email="c21-inv@test.local",
        password_hash=hash_password("Demo@12345"),
        role="INVIGILATOR",
        is_active=True,
    )
    hod = User(
        name="C21 HOD",
        email="c21-hod@test.local",
        password_hash=hash_password("Demo@12345"),
        role="HOD",
        is_active=True,
    )
    dec = User(
        name="C21 DEC",
        email="c21-dec@test.local",
        password_hash=hash_password("Demo@12345"),
        role="DEC",
        is_active=True,
    )
    exam_dept = User(
        name="C21 Exam",
        email="c21-exam@test.local",
        password_hash=hash_password("Demo@12345"),
        role="EXAM_DEPARTMENT",
        is_active=True,
    )
    ufm = User(
        name="C21 UFM",
        email="c21-ufm@test.local",
        password_hash=hash_password("Demo@12345"),
        role="UFM_COMMITTEE",
        is_active=True,
    )
    student_user = User(
        name="C21 Student User",
        email="c21-stu@test.local",
        password_hash=hash_password("Demo@12345"),
        role="STUDENT",
        is_active=True,
    )
    db.add_all([inv, hod, dec, exam_dept, ufm, student_user])
    db.flush()

    room = ExamRoom(room_number="C21-R1", building="Block A", capacity=40)
    db.add(room)
    db.flush()

    student = Student(
        student_id="C21-ROLL",
        name="C21 Student",
        department="CS",
        program="BSCS",
        user_id=student_user.id,
    )
    exam = Exam(
        course_code="C21EX",
        course_name="C21 Exam",
        semester="Fall",
        exam_date=datetime(2026, 10, 3).date(),
        start_time=datetime(2026, 10, 3, 9, 0).time(),
        end_time=datetime(2026, 10, 3, 12, 0).time(),
        room_id=room.id,
    )
    db.add_all([student, exam])
    db.commit()
    for u in (inv, hod, dec, exam_dept, ufm, student_user):
        db.refresh(u)
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
        "hod": hod,
        "dec": dec,
        "exam_dept": exam_dept,
        "ufm": ufm,
        "student_user": student_user,
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


def _add_case(
    db,
    *,
    student_id: int,
    exam_id: int,
    reported_by: int,
    status: str,
    created_at: datetime,
    case_number: str,
    violation: str = "MOBILE_PHONE",
) -> UfmCase:
    row = UfmCase(
        case_number=case_number,
        student_id=student_id,
        exam_id=exam_id,
        reported_by=reported_by,
        violation_type=violation,
        description=f"C21 {case_number}",
        status=status,
        created_at=created_at,
        updated_at=created_at,
        signer_name="C21",
        signature_ack=True,
        signed_at=created_at,
    )
    db.add(row)
    db.flush()
    return row


def test_list_cases_newest_first(client_db):
    db = client_db["db"]
    older = datetime(2026, 10, 1, 10, 0, 0)
    newer = datetime(2026, 10, 3, 15, 30, 0)
    _add_case(
        db,
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        status="PENDING",
        created_at=older,
        case_number="C21-OLD",
    )
    _add_case(
        db,
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        status="PENDING",
        created_at=newer,
        case_number="C21-NEW",
    )
    db.commit()

    r = client_db["client"].get(
        "/ufm-cases", headers=_h(client_db["token"](client_db["hod"]))
    )
    assert r.status_code == 200
    body = r.json()
    nums = [c["case_number"] for c in body]
    assert nums.index("C21-NEW") < nums.index("C21-OLD")


def test_list_cases_multiple_and_tie_breaker(client_db):
    db = client_db["db"]
    t0 = datetime(2026, 9, 1, 8, 0, 0)
    t1 = datetime(2026, 9, 2, 8, 0, 0)
    t2 = datetime(2026, 9, 3, 8, 0, 0)
    same = datetime(2026, 9, 4, 12, 0, 0)

    _add_case(
        db,
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        status="PENDING",
        created_at=t0,
        case_number="C21-A",
    )
    _add_case(
        db,
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        status="PENDING",
        created_at=t1,
        case_number="C21-B",
    )
    _add_case(
        db,
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        status="PENDING",
        created_at=t2,
        case_number="C21-C",
    )
    tie_lo = _add_case(
        db,
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        status="PENDING",
        created_at=same,
        case_number="C21-TIE-LO",
    )
    tie_hi = _add_case(
        db,
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        status="PENDING",
        created_at=same,
        case_number="C21-TIE-HI",
    )
    db.commit()
    assert tie_hi.id > tie_lo.id

    r = client_db["client"].get(
        "/ufm-cases", headers=_h(client_db["token"](client_db["hod"]))
    )
    assert r.status_code == 200
    nums = [c["case_number"] for c in r.json()]
    assert nums.index("C21-C") < nums.index("C21-B") < nums.index("C21-A")
    assert nums.index("C21-TIE-HI") < nums.index("C21-TIE-LO")


def test_status_filter_preserves_newest_first(client_db):
    """Role queues filter client-side; API order must already be newest-first."""
    db = client_db["db"]
    _add_case(
        db,
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        status="DEC_REVIEW",
        created_at=datetime(2026, 8, 1, 9, 0, 0),
        case_number="C21-DEC-OLD",
    )
    _add_case(
        db,
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        status="PENDING",
        created_at=datetime(2026, 8, 3, 9, 0, 0),
        case_number="C21-PEND",
    )
    _add_case(
        db,
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=client_db["inv"].id,
        status="DEC_REVIEW",
        created_at=datetime(2026, 8, 5, 9, 0, 0),
        case_number="C21-DEC-NEW",
    )
    db.commit()

    r = client_db["client"].get(
        "/ufm-cases", headers=_h(client_db["token"](client_db["dec"]))
    )
    assert r.status_code == 200
    dec_only = [c for c in r.json() if c["status"] == "DEC_REVIEW"]
    assert [c["case_number"] for c in dec_only] == [
        "C21-DEC-NEW",
        "C21-DEC-OLD",
    ]


def test_role_queues_latest_first(client_db):
    db = client_db["db"]
    base = datetime(2026, 7, 1, 10, 0, 0)
    specs = [
        ("PENDING", "C21-HOD-OLD", base),
        ("PENDING", "C21-HOD-NEW", base + timedelta(days=2)),
        ("DEC_REVIEW", "C21-DEC-OLD", base + timedelta(days=1)),
        ("DEC_REVIEW", "C21-DEC-NEW", base + timedelta(days=3)),
        ("EXAM_DEPARTMENT_REVIEW", "C21-EX-OLD", base),
        ("EXAM_DEPARTMENT_REVIEW", "C21-EX-NEW", base + timedelta(days=4)),
        ("UFM_COMMITTEE_REVIEW", "C21-UFM-OLD", base),
        ("UFM_COMMITTEE_REVIEW", "C21-UFM-NEW", base + timedelta(days=5)),
    ]
    for status, num, ts in specs:
        _add_case(
            db,
            student_id=client_db["student"].id,
            exam_id=client_db["exam"].id,
            reported_by=client_db["inv"].id,
            status=status,
            created_at=ts,
            case_number=num,
        )
    db.commit()

    checks = [
        (client_db["hod"], "PENDING", ["C21-HOD-NEW", "C21-HOD-OLD"]),
        (client_db["dec"], "DEC_REVIEW", ["C21-DEC-NEW", "C21-DEC-OLD"]),
        (
            client_db["exam_dept"],
            "EXAM_DEPARTMENT_REVIEW",
            ["C21-EX-NEW", "C21-EX-OLD"],
        ),
        (
            client_db["ufm"],
            "UFM_COMMITTEE_REVIEW",
            ["C21-UFM-NEW", "C21-UFM-OLD"],
        ),
        (client_db["inv"], None, None),  # inv sees own reported cases
        (client_db["student_user"], None, None),
    ]

    for user, status, expected in checks:
        r = client_db["client"].get(
            "/ufm-cases", headers=_h(client_db["token"](user))
        )
        assert r.status_code == 200, user.role
        body = r.json()
        created = [
            datetime.fromisoformat(c["created_at"].replace("Z", ""))
            for c in body
        ]
        assert created == sorted(created, reverse=True), user.role
        ids = [c["id"] for c in body]
        # Tie-break stability within equal timestamps
        for i in range(len(body) - 1):
            if created[i] == created[i + 1]:
                assert ids[i] > ids[i + 1], user.role
        if status and expected:
            filtered = [c["case_number"] for c in body if c["status"] == status]
            assert filtered == expected, user.role


def test_dec_dashboard_label_cases_received_from_hod():
    if not DASHBOARD_BY_ROLE.is_file():
        pytest.skip("Frontend sources not mounted")
    dash = DASHBOARD_BY_ROLE.read_text(encoding="utf-8")
    dec_actions = (
        dash.split("export function quickActionsForRole")[1]
        .split('if (role === "DEC")')[1]
        .split('if (role === "EXAM_DEPARTMENT")')[0]
    )
    assert 'label: "Cases Received from HOD"' in dec_actions
    assert "DEC Review Queue" not in dec_actions

    queue_meta = (
        dash.split("export function queueMetaForRole")[1]
        .split('if (role === "DEC")')[1]
        .split('if (role === "EXAM_DEPARTMENT")')[0]
    )
    assert 'title: "Cases Received from HOD"' in queue_meta

    if NAV_BY_ROLE.is_file():
        nav = NAV_BY_ROLE.read_text(encoding="utf-8")
        dec_nav = nav.split("DEC: [")[1].split("EXAM_DEPARTMENT: [")[0]
        assert "Cases Received from HOD" in dec_nav
        assert "DEC Review Queue" not in dec_nav
