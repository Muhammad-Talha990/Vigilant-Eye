"""
C22 — role-scoped case dashboard / list visibility.

  pytest -q tests/test_case_visibility_c22.py
"""

from __future__ import annotations

from datetime import datetime

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

    users = {}
    for key, role, email in [
        ("inv", "INVIGILATOR", "c22-inv@test.local"),
        ("hod", "HOD", "c22-hod@test.local"),
        ("dec", "DEC", "c22-dec@test.local"),
        ("exam", "EXAM_DEPARTMENT", "c22-exam@test.local"),
        ("ufm", "UFM_COMMITTEE", "c22-ufm@test.local"),
        ("stu", "STUDENT", "c22-stu@test.local"),
    ]:
        u = User(
            name=f"C22 {role}",
            email=email,
            password_hash=hash_password("Demo@12345"),
            role=role,
            is_active=True,
        )
        db.add(u)
        users[key] = u
    db.flush()

    room = ExamRoom(room_number="C22-R1", building="A", capacity=40)
    db.add(room)
    db.flush()
    student = Student(
        student_id="C22-ROLL",
        name="C22 Student",
        department="CS",
        program="BSCS",
        user_id=users["stu"].id,
    )
    exam = Exam(
        course_code="C22EX",
        course_name="C22 Exam",
        semester="Fall",
        exam_date=datetime(2026, 10, 3).date(),
        start_time=datetime(2026, 10, 3, 9, 0).time(),
        end_time=datetime(2026, 10, 3, 12, 0).time(),
        room_id=room.id,
    )
    db.add_all([student, exam])
    db.commit()
    for u in users.values():
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
        "token": token,
        "users": users,
        "student": student,
        "exam": exam,
    }

    app.dependency_overrides.clear()
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _ids(resp) -> set[int]:
    assert resp.status_code == 200, resp.text
    return {c["id"] for c in resp.json()}


def _sign(action: str, remarks: str = "ok") -> dict:
    return {
        "action": action,
        "remarks": remarks,
        "signer_name": "C22 Reviewer",
        "signature_ack": True,
    }


def _create_case(client_db) -> int:
    c = client_db["client"]
    inv = client_db["users"]["inv"]
    r = c.post(
        "/ufm-cases",
        headers=_h(client_db["token"](inv)),
        json={
            "student_id": client_db["student"].id,
            "exam_id": client_db["exam"].id,
            "violation_type": "MOBILE_PHONE",
            "description": "C22 visibility scenario",
            "recovered_materials": ["MOBILE_PHONE"],
            "signer_name": "C22 Inv",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_new_case_visible_only_to_inv_and_hod(client_db):
    case_id = _create_case(client_db)
    c = client_db["client"]
    t = client_db["token"]
    u = client_db["users"]

    assert case_id in _ids(c.get("/ufm-cases", headers=_h(t(u["inv"]))))
    assert case_id in _ids(c.get("/ufm-cases", headers=_h(t(u["hod"]))))
    assert case_id not in _ids(c.get("/ufm-cases", headers=_h(t(u["dec"]))))
    assert case_id not in _ids(c.get("/ufm-cases", headers=_h(t(u["exam"]))))
    assert case_id not in _ids(c.get("/ufm-cases", headers=_h(t(u["ufm"]))))

    # Active queue endpoint also hides from downstream
    assert case_id not in _ids(
        c.get("/ufm-cases?scope=active", headers=_h(t(u["dec"])))
    )
    assert case_id in _ids(
        c.get("/ufm-cases?scope=active", headers=_h(t(u["hod"])))
    )


def test_forward_chain_visibility(client_db):
    case_id = _create_case(client_db)
    c = client_db["client"]
    t = client_db["token"]
    u = client_db["users"]

    # HOD → DEC
    assert (
        c.post(
            f"/ufm-cases/{case_id}/reviews",
            headers=_h(t(u["hod"])),
            json=_sign("FORWARD"),
        ).status_code
        == 201
    )
    assert case_id in _ids(c.get("/ufm-cases", headers=_h(t(u["dec"]))))
    assert case_id not in _ids(c.get("/ufm-cases", headers=_h(t(u["exam"]))))
    assert case_id not in _ids(c.get("/ufm-cases", headers=_h(t(u["ufm"]))))
    # HOD active queue no longer owns it
    assert case_id not in _ids(
        c.get("/ufm-cases?scope=active", headers=_h(t(u["hod"])))
    )
    assert case_id in _ids(
        c.get("/ufm-cases?scope=active", headers=_h(t(u["dec"])))
    )

    # DEC → Exam
    assert (
        c.post(
            f"/ufm-cases/{case_id}/reviews",
            headers=_h(t(u["dec"])),
            json=_sign("FORWARD"),
        ).status_code
        == 201
    )
    assert case_id in _ids(c.get("/ufm-cases", headers=_h(t(u["exam"]))))
    assert case_id not in _ids(c.get("/ufm-cases", headers=_h(t(u["ufm"]))))
    assert case_id not in _ids(
        c.get("/ufm-cases?scope=active", headers=_h(t(u["dec"])))
    )

    # Exam → UFM
    assert (
        c.post(
            f"/ufm-cases/{case_id}/reviews",
            headers=_h(t(u["exam"])),
            json=_sign("FORWARD"),
        ).status_code
        == 201
    )
    assert case_id in _ids(c.get("/ufm-cases", headers=_h(t(u["ufm"]))))
    assert case_id in _ids(
        c.get("/ufm-cases?scope=active", headers=_h(t(u["ufm"])))
    )


def test_return_restores_hod_hides_downstream(client_db):
    case_id = _create_case(client_db)
    c = client_db["client"]
    t = client_db["token"]
    u = client_db["users"]

    c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(t(u["hod"])),
        json=_sign("FORWARD"),
    )
    c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(t(u["dec"])),
        json=_sign("RETURN", "send back"),
    )

    assert case_id in _ids(
        c.get("/ufm-cases?scope=active", headers=_h(t(u["hod"])))
    )
    assert case_id not in _ids(c.get("/ufm-cases", headers=_h(t(u["dec"]))))
    assert case_id not in _ids(c.get("/ufm-cases", headers=_h(t(u["exam"]))))
    assert case_id not in _ids(c.get("/ufm-cases", headers=_h(t(u["ufm"]))))


def test_status_query_cannot_bypass_scope(client_db):
    case_id = _create_case(client_db)
    c = client_db["client"]
    t = client_db["token"]
    dec = client_db["users"]["dec"]

    # DEC must not pull PENDING via status filter
    r = c.get(
        "/ufm-cases?scope=dashboard&status=PENDING",
        headers=_h(t(dec)),
    )
    assert r.status_code == 200
    assert case_id not in {x["id"] for x in r.json()}

    r2 = c.get(
        "/ufm-cases?scope=active&status=PENDING",
        headers=_h(t(dec)),
    )
    assert r2.status_code == 200
    assert case_id not in {x["id"] for x in r2.json()}


def test_dashboard_counts_match_visible_active(client_db):
    case_id = _create_case(client_db)
    c = client_db["client"]
    t = client_db["token"]
    u = client_db["users"]

    dec_active = c.get(
        "/ufm-cases?scope=active", headers=_h(t(u["dec"]))
    ).json()
    assert all(x["status"] == "DEC_REVIEW" for x in dec_active)
    assert case_id not in {x["id"] for x in dec_active}

    # After forward, active count includes the case
    c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(t(u["hod"])),
        json=_sign("FORWARD"),
    )
    dec_active2 = c.get(
        "/ufm-cases?scope=active", headers=_h(t(u["dec"]))
    ).json()
    assert case_id in {x["id"] for x in dec_active2}


def test_latest_first_preserved_in_scoped_lists(client_db):
    db = client_db["db"]
    inv = client_db["users"]["inv"]
    older = UfmCase(
        case_number="C22-OLD",
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=inv.id,
        violation_type="MOBILE_PHONE",
        description="old",
        status="DEC_REVIEW",
        created_at=datetime(2026, 9, 1, 10, 0, 0),
        updated_at=datetime(2026, 9, 1, 10, 0, 0),
        signer_name="x",
        signature_ack=True,
    )
    newer = UfmCase(
        case_number="C22-NEW",
        student_id=client_db["student"].id,
        exam_id=client_db["exam"].id,
        reported_by=inv.id,
        violation_type="MOBILE_PHONE",
        description="new",
        status="DEC_REVIEW",
        created_at=datetime(2026, 10, 1, 10, 0, 0),
        updated_at=datetime(2026, 10, 1, 10, 0, 0),
        signer_name="x",
        signature_ack=True,
    )
    db.add_all([older, newer])
    db.commit()

    r = client_db["client"].get(
        "/ufm-cases?scope=active",
        headers=_h(client_db["token"](client_db["users"]["dec"])),
    )
    assert r.status_code == 200
    nums = [x["case_number"] for x in r.json()]
    assert nums.index("C22-NEW") < nums.index("C22-OLD")


def test_invigilator_sees_own_cases_only(client_db):
    case_id = _create_case(client_db)
    # Second invigilator
    other = User(
        name="Other Inv",
        email="c22-inv2@test.local",
        password_hash=hash_password("Demo@12345"),
        role="INVIGILATOR",
        is_active=True,
    )
    client_db["db"].add(other)
    client_db["db"].commit()
    client_db["db"].refresh(other)

    c = client_db["client"]
    mine = _ids(
        c.get(
            "/ufm-cases",
            headers=_h(client_db["token"](client_db["users"]["inv"])),
        )
    )
    theirs = _ids(
        c.get("/ufm-cases", headers=_h(client_db["token"](other)))
    )
    assert case_id in mine
    assert case_id not in theirs

    # Detail + evidence must enforce the same ownership boundary (not list-only).
    owner_h = _h(client_db["token"](client_db["users"]["inv"]))
    other_h = _h(client_db["token"](other))
    assert c.get(f"/ufm-cases/{case_id}", headers=owner_h).status_code == 200
    assert c.get(f"/ufm-cases/{case_id}", headers=other_h).status_code == 403


def test_downstream_roles_cannot_open_pending_to_under_review(client_db):
    """CASE_OPENED (PENDING→UNDER_REVIEW) is HOD-only; DEC/Exam/UFM must not mutate."""
    case_id = _create_case(client_db)
    c = client_db["client"]
    t = client_db["token"]
    u = client_db["users"]

    for role_key in ("dec", "exam", "ufm"):
        r = c.get(f"/ufm-cases/{case_id}", headers=_h(t(u[role_key])))
        # Institutional reviewers may still read the record, but status must stay PENDING.
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "PENDING"

    hod_r = c.get(f"/ufm-cases/{case_id}", headers=_h(t(u["hod"])))
    assert hod_r.status_code == 200
    assert hod_r.json()["status"] == "UNDER_REVIEW"
