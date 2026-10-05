"""Phase C7 — department/semester report fields via authoritative case list."""

from __future__ import annotations

from collections import Counter
from datetime import date, time

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

UNKNOWN = "Unknown/Not recorded"


def _aggregate(cases: list[dict], field: str) -> dict[str, int]:
    """Mirror frontend reportStats.countCasesByField."""
    counts: Counter[str] = Counter()
    for row in cases:
        raw = row.get(field)
        if raw is None or str(raw).strip() == "":
            key = UNKNOWN
        else:
            key = str(raw).strip()
        counts[key] += 1
    return dict(counts)


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

    room = ExamRoom(room_number="RPT-R1", building="Block A", capacity=40)
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

    inv = add_user(email="invig.report.c7@demo.com", role="INVIGILATOR", name="Invig Rpt")
    student_cs_user = add_user(
        email="stu.cs.c7@demo.com", role="STUDENT", name="Stu CS"
    )
    student_ee_user = add_user(
        email="stu.ee.c7@demo.com", role="STUDENT", name="Stu EE"
    )
    student_unk_user = add_user(
        email="stu.unk.c7@demo.com", role="STUDENT", name="Stu Unk"
    )
    admin = add_user(
        email="admin.report.c7@demo.com", role="ADMINISTRATOR", name="Admin Rpt"
    )

    stu_cs = Student(
        student_id="RPTCS01",
        name="CS Student",
        department="CS",
        program="BSCS",
        user_id=student_cs_user.id,
    )
    stu_ee = Student(
        student_id="RPTEE01",
        name="EE Student",
        department="EE",
        program="BSEE",
        user_id=student_ee_user.id,
    )
    stu_unk = Student(
        student_id="RPTUNK01",
        name="No Dept Student",
        department="",
        program="BS",
        user_id=student_unk_user.id,
    )
    exam_fall = Exam(
        course_code="RPT101",
        course_name="Fall Exam",
        semester="Fall 2025",
        exam_date=date(2025, 11, 1),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    exam_spring = Exam(
        course_code="RPT102",
        course_name="Spring Exam",
        semester="Spring 2026",
        exam_date=date(2026, 3, 1),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    exam_blank = Exam(
        course_code="RPT103",
        course_name="Blank Semester Exam",
        semester="",
        exam_date=date(2026, 4, 1),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    db.add_all([stu_cs, stu_ee, stu_unk, exam_fall, exam_spring, exam_blank])
    db.commit()
    for obj in (stu_cs, stu_ee, stu_unk, exam_fall, exam_spring, exam_blank):
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
        "student_cs_user": student_cs_user,
        "stu_cs": stu_cs,
        "stu_ee": stu_ee,
        "stu_unk": stu_unk,
        "exam_fall": exam_fall,
        "exam_spring": exam_spring,
        "exam_blank": exam_blank,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _add_case(ctx, *, student, exam, case_number):
    db = ctx["db"]
    case = UfmCase(
        case_number=case_number,
        student_id=student.id,
        exam_id=exam.id,
        reported_by=ctx["inv"].id,
        violation_type="MOBILE_PHONE",
        description=f"Report case {case_number}",
        status="PENDING",
        signer_name="Invig Rpt",
        signature_ack=True,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def test_department_and_semester_stats_from_case_list(client_db):
    _add_case(
        client_db,
        student=client_db["stu_cs"],
        exam=client_db["exam_fall"],
        case_number="UFM-RPT-1",
    )
    _add_case(
        client_db,
        student=client_db["stu_cs"],
        exam=client_db["exam_fall"],
        case_number="UFM-RPT-2",
    )
    _add_case(
        client_db,
        student=client_db["stu_ee"],
        exam=client_db["exam_spring"],
        case_number="UFM-RPT-3",
    )

    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    r = c.get("/ufm-cases", headers=h)
    assert r.status_code == 200
    cases = r.json()
    assert len(cases) == 3

    # Existing report KPIs (total) unchanged in meaning
    assert len(cases) == 3

    depts = _aggregate(cases, "student_department")
    assert depts == {"CS": 2, "EE": 1}

    semesters = _aggregate(cases, "exam_semester")
    assert semesters == {"Fall 2025": 2, "Spring 2026": 1}

    for row in cases:
        assert "student_department" in row
        assert "exam_semester" in row


def test_missing_department_and_semester_group_as_unknown(client_db):
    _add_case(
        client_db,
        student=client_db["stu_unk"],
        exam=client_db["exam_blank"],
        case_number="UFM-RPT-UNK",
    )
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    cases = c.get("/ufm-cases", headers=h).json()
    assert len(cases) == 1
    assert cases[0]["student_department"] in (None, "")
    assert cases[0]["exam_semester"] in (None, "")
    assert _aggregate(cases, "student_department") == {UNKNOWN: 1}
    assert _aggregate(cases, "exam_semester") == {UNKNOWN: 1}


def test_administrator_still_sees_empty_case_list_for_reports_source(client_db):
    _add_case(
        client_db,
        student=client_db["stu_cs"],
        exam=client_db["exam_fall"],
        case_number="UFM-RPT-ADM",
    )
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    r = c.get("/ufm-cases", headers=h)
    assert r.status_code == 200
    assert r.json() == []


def test_student_isolation_still_limits_case_list(client_db):
    _add_case(
        client_db,
        student=client_db["stu_cs"],
        exam=client_db["exam_fall"],
        case_number="UFM-RPT-ISO",
    )
    _add_case(
        client_db,
        student=client_db["stu_ee"],
        exam=client_db["exam_spring"],
        case_number="UFM-RPT-ISO2",
    )
    c = client_db["client"]
    h = _h(client_db["token"](client_db["student_cs_user"]))
    r = c.get("/ufm-cases", headers=h)
    assert r.status_code == 200
    cases = r.json()
    assert len(cases) == 1
    assert cases[0]["student_department"] == "CS"
