"""Phase 26 — UFM lifecycle: workflow, clarification, result control, authz."""

from __future__ import annotations

from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models.audit_log import AuditLog
from models.base import Base
from models.case_review import CaseReview
from models.clarification import Clarification
from models.exam import Exam
from models.exam_room import ExamRoom
from models.notification import Notification
from models.result_control import ResultControl
from models.student import Student
from models.ufm_case import UfmCase
from models.user import User
from security import create_access_token, hash_password
from workflow import WORKFLOW, next_status


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

    room = ExamRoom(room_number="P26-R1", building="Block A", capacity=40)
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

    inv = add_user(email="inv.p26@demo.com", role="INVIGILATOR", name="Inv P26")
    hod = add_user(email="hod.p26@demo.com", role="HOD", name="Hod P26")
    dec = add_user(email="dec.p26@demo.com", role="DEC", name="Dec P26")
    exam = add_user(email="exam.p26@demo.com", role="EXAM_DEPARTMENT", name="Exam P26")
    ufm = add_user(email="ufm.p26@demo.com", role="UFM_COMMITTEE", name="Ufm P26")
    stu_user = add_user(email="stu.p26@demo.com", role="STUDENT", name="Stu P26")
    stu_b_user = add_user(email="stub.p26@demo.com", role="STUDENT", name="StuB P26")
    admin = add_user(email="admin.p26@demo.com", role="ADMINISTRATOR", name="Admin P26")

    student = Student(
        student_id="P26STU01",
        name="Phase26 Student",
        department="CS",
        program="BSCS",
        user_id=stu_user.id,
    )
    student_b = Student(
        student_id="P26STU02",
        name="Phase26 Other",
        department="CS",
        program="BSCS",
        user_id=stu_b_user.id,
    )
    exam_row = Exam(
        course_code="P26101",
        course_name="Phase26 Exam",
        semester="Fall",
        exam_date=date(2026, 9, 30),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    db.add_all([student, student_b, exam_row])
    db.commit()
    db.refresh(student)
    db.refresh(student_b)
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
        "stu_user": stu_user,
        "stu_b_user": stu_b_user,
        "admin": admin,
        "student": student,
        "student_b": student_b,
        "exam_row": exam_row,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _sign(action: str, remarks: str = "phase26") -> dict:
    return {
        "action": action,
        "remarks": remarks,
        "signer_name": "Phase26 Reviewer",
        "signature_ack": True,
    }


def _create_case(client_db, *, student=None) -> dict:
    c = client_db["client"]
    h = _h(client_db["token"](client_db["inv"]))
    stu = student or client_db["student"]
    r = c.post(
        "/ufm-cases",
        headers=h,
        json={
            "student_id": stu.id,
            "exam_id": client_db["exam_row"].id,
            "violation_type": "OTHER",
            "description": "Phase 26 controlled UFM case for lifecycle tests.",
            "recovered_materials": ["MOBILE_PHONE"],
            "signer_name": "Invigilator Phase26",
            "signature_ack": True,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_case_create_notifies_exam_and_ufm_committee(client_db):
    """CASE_CREATED goes to HOD, Exam Dept, UFM Committee, and linked student."""
    db = client_db["db"]

    inactive_exam = User(
        name="Inactive Exam",
        email="exam.inactive.p26@demo.com",
        password_hash=hash_password("UnusedPass1!"),
        role="EXAM_DEPARTMENT",
        is_active=False,
    )
    inactive_ufm = User(
        name="Inactive Ufm",
        email="ufm.inactive.p26@demo.com",
        password_hash=hash_password("UnusedPass1!"),
        role="UFM_COMMITTEE",
        is_active=False,
    )
    db.add_all([inactive_exam, inactive_ufm])
    db.commit()
    db.refresh(inactive_exam)
    db.refresh(inactive_ufm)

    case = _create_case(client_db)
    case_id = case["id"]
    db.expire_all()

    notes = db.scalars(
        select(Notification).where(
            Notification.case_id == case_id,
            Notification.type == "CASE_CREATED",
        )
    ).all()
    by_user = {n.user_id: n for n in notes}

    assert client_db["hod"].id in by_user
    assert client_db["exam"].id in by_user
    assert client_db["ufm"].id in by_user
    assert client_db["stu_user"].id in by_user

    assert inactive_exam.id not in by_user
    assert inactive_ufm.id not in by_user

    assert by_user[client_db["hod"].id].title == "New UFM case"
    assert by_user[client_db["exam"].id].title == "New UFM case"
    assert by_user[client_db["ufm"].id].title == "New UFM case"
    assert by_user[client_db["stu_user"].id].title == "UFM case filed"

    for uid in (
        client_db["hod"].id,
        client_db["exam"].id,
        client_db["ufm"].id,
        client_db["stu_user"].id,
    ):
        assert case["case_number"] in by_user[uid].message

    # DEC is not a create-time recipient
    assert client_db["dec"].id not in by_user


def test_workflow_table_matches_documented_chain():
    assert set(WORKFLOW.keys()) == {
        "HOD",
        "DEC",
        "EXAM_DEPARTMENT",
        "UFM_COMMITTEE",
    }
    assert next_status(role="HOD", action="FORWARD", current_status="PENDING") == (
        "DEC_REVIEW"
    )
    assert next_status(
        role="HOD", action="FORWARD", current_status="UNDER_REVIEW"
    ) == "DEC_REVIEW"
    assert next_status(
        role="DEC", action="FORWARD", current_status="DEC_REVIEW"
    ) == "EXAM_DEPARTMENT_REVIEW"
    assert next_status(
        role="EXAM_DEPARTMENT",
        action="FORWARD",
        current_status="EXAM_DEPARTMENT_REVIEW",
    ) == "UFM_COMMITTEE_REVIEW"
    assert next_status(
        role="UFM_COMMITTEE",
        action="APPROVE",
        current_status="UFM_COMMITTEE_REVIEW",
    ) == "APPROVED"
    assert next_status(
        role="UFM_COMMITTEE",
        action="REJECT",
        current_status="UFM_COMMITTEE_REVIEW",
    ) == "REJECTED"


def test_invalid_transitions_rejected():
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        next_status(role="INVIGILATOR", action="FORWARD", current_status="PENDING")
    assert ei.value.status_code == 403

    with pytest.raises(HTTPException) as ei:
        next_status(role="HOD", action="APPROVE", current_status="PENDING")
    assert ei.value.status_code == 400

    with pytest.raises(HTTPException) as ei:
        next_status(
            role="UFM_COMMITTEE",
            action="APPROVE",
            current_status="PENDING",
        )
    assert ei.value.status_code == 400

    with pytest.raises(HTTPException) as ei:
        next_status(role="DEC", action="FORWARD", current_status="APPROVED")
    assert ei.value.status_code == 400


def test_hod_verification_not_active_workflow_status():
    """HOD_VERIFICATION is obsolete — never a transition target or RETURN source."""
    from fastapi import HTTPException

    # Not produced by any FORWARD/APPROVE/REJECT rule
    for role_rules in WORKFLOW.values():
        for _action, (_allowed, new_status) in role_rules.items():
            assert new_status != "HOD_VERIFICATION"

    # HOD cannot RETURN from HOD_VERIFICATION (not an active state)
    with pytest.raises(HTTPException) as ei:
        next_status(
            role="HOD",
            action="RETURN",
            current_status="HOD_VERIFICATION",
        )
    assert ei.value.status_code == 400

    # Legitimate RETURN sources still work
    assert (
        next_status(role="HOD", action="RETURN", current_status="DEC_REVIEW")
        == "PENDING"
    )
    assert (
        next_status(role="HOD", action="RETURN", current_status="UNDER_REVIEW")
        == "PENDING"
    )


def test_full_lifecycle_approve_hold_release(client_db):
    c = client_db["client"]
    case = _create_case(client_db)
    case_id = case["id"]

    # HOD open → UNDER_REVIEW
    r = c.get(f"/ufm-cases/{case_id}", headers=_h(client_db["token"](client_db["hod"])))
    assert r.status_code == 200
    assert r.json()["status"] == "UNDER_REVIEW"

    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["hod"])),
        json=_sign("FORWARD", "to DEC"),
    )
    assert r.status_code == 201

    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["dec"])),
        json=_sign("FORWARD", "to Exam"),
    )
    assert r.status_code == 201

    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["exam"])),
        json=_sign("FORWARD", "to Committee"),
    )
    assert r.status_code == 201

    # Invigilator cannot decide
    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["inv"])),
        json=_sign("APPROVE"),
    )
    assert r.status_code == 403

    # Admin cannot decide
    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["admin"])),
        json=_sign("APPROVE"),
    )
    assert r.status_code == 403

    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["ufm"])),
        json=_sign("APPROVE", "sustained"),
    )
    assert r.status_code == 201

    db = client_db["db"]
    db.expire_all()
    ufm_case = db.get(UfmCase, case_id)
    assert ufm_case.status == "APPROVED"

    hold = db.scalar(select(ResultControl).where(ResultControl.case_id == case_id))
    assert hold is not None
    assert hold.result_status == "HELD"
    assert hold.transcript_status == "BLOCKED"

    # Duplicate hold rejected
    r = c.post(
        "/result-controls",
        headers=_h(client_db["token"](client_db["exam"])),
        json={
            "student_id": client_db["student"].id,
            "case_id": case_id,
            "result_status": "HELD",
            "transcript_status": "BLOCKED",
            "reason": "dup",
        },
    )
    assert r.status_code == 400

    # Unauthorized release
    r = c.patch(
        f"/result-controls/{hold.id}/release",
        headers=_h(client_db["token"](client_db["hod"])),
    )
    assert r.status_code == 403

    r = c.patch(
        f"/result-controls/{hold.id}/release",
        headers=_h(client_db["token"](client_db["exam"])),
    )
    assert r.status_code == 200
    assert r.json()["result_status"] == "RELEASED"

    r = c.patch(
        f"/result-controls/{hold.id}/release",
        headers=_h(client_db["token"](client_db["exam"])),
    )
    assert r.status_code == 400

    reviews = db.scalars(
        select(CaseReview).where(CaseReview.case_id == case_id).order_by(CaseReview.id)
    ).all()
    assert [x.action for x in reviews] == [
        "FORWARD",
        "FORWARD",
        "FORWARD",
        "APPROVE",
    ]

    audits = db.scalars(
        select(AuditLog).where(AuditLog.entity_type == "ufm_case")
    ).all()
    actions = {a.action for a in audits if str(a.entity_id) == str(case_id)}
    assert "CASE_REVIEW_APPROVE" in actions or any(
        "APPROVE" in (a.action or "") for a in audits
    )


def test_clarification_once_and_isolation(client_db):
    c = client_db["client"]
    case_a = _create_case(client_db)
    case_b = _create_case(client_db, student=client_db["student_b"])

    # Student B cannot access student A case
    r = c.get(
        f"/ufm-cases/{case_a['id']}",
        headers=_h(client_db["token"](client_db["stu_b_user"])),
    )
    assert r.status_code == 403

    r = c.post(
        "/clarifications",
        headers=_h(client_db["token"](client_db["stu_user"])),
        json={"case_id": case_b["id"], "statement": "Trying other student case xx"},
    )
    assert r.status_code == 403

    r = c.post(
        "/clarifications",
        headers=_h(client_db["token"](client_db["stu_user"])),
        json={"case_id": case_a["id"], "statement": "My clarification statement here."},
    )
    assert r.status_code == 201

    r = c.post(
        "/clarifications",
        headers=_h(client_db["token"](client_db["stu_user"])),
        json={"case_id": case_a["id"], "statement": "Duplicate clarification attempt."},
    )
    assert r.status_code == 400

    # Student cannot read reviews
    r = c.get(
        f"/ufm-cases/{case_a['id']}/reviews",
        headers=_h(client_db["token"](client_db["stu_user"])),
    )
    assert r.status_code == 403

    db = client_db["db"]
    hod_notes = db.scalars(
        select(Notification).where(
            Notification.user_id == client_db["hod"].id,
            Notification.type == "CLARIFICATION",
            Notification.case_id == case_a["id"],
        )
    ).all()
    assert len(hod_notes) >= 1


def test_return_path_and_finalized_locked(client_db):
    c = client_db["client"]
    case = _create_case(client_db)
    case_id = case["id"]

    c.get(f"/ufm-cases/{case_id}", headers=_h(client_db["token"](client_db["hod"])))
    c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["hod"])),
        json=_sign("FORWARD"),
    )
    # DEC RETURN → PENDING
    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["dec"])),
        json=_sign("RETURN", "needs more info"),
    )
    assert r.status_code == 201
    assert (
        client_db["client"]
        .get(f"/ufm-cases/{case_id}", headers=_h(client_db["token"](client_db["hod"])))
        .json()["status"]
        in ("PENDING", "UNDER_REVIEW")
    )

    # Re-drive to APPROVED then lock
    status = c.get(
        f"/ufm-cases/{case_id}", headers=_h(client_db["token"](client_db["hod"]))
    ).json()["status"]
    if status in ("PENDING", "UNDER_REVIEW"):
        c.post(
            f"/ufm-cases/{case_id}/reviews",
            headers=_h(client_db["token"](client_db["hod"])),
            json=_sign("FORWARD"),
        )
    c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["dec"])),
        json=_sign("FORWARD"),
    )
    c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["exam"])),
        json=_sign("FORWARD"),
    )
    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["ufm"])),
        json=_sign("REJECT", "not sustained"),
    )
    assert r.status_code == 201

    r = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=_h(client_db["token"](client_db["ufm"])),
        json=_sign("APPROVE"),
    )
    assert r.status_code == 400


def test_admin_isolated_from_cases(client_db):
    c = client_db["client"]
    case = _create_case(client_db)
    h = _h(client_db["token"](client_db["admin"]))
    assert c.get(f"/ufm-cases/{case['id']}", headers=h).status_code == 403
    listed = c.get("/ufm-cases", headers=h)
    assert listed.status_code == 200
    assert listed.json() == []
    assert (
        c.post(
            f"/ufm-cases/{case['id']}/reviews",
            headers=h,
            json=_sign("FORWARD"),
        ).status_code
        == 403
    )


def test_forged_jwt_role_uses_db_role(client_db):
    c = client_db["client"]
    case = _create_case(client_db)
    forged = create_access_token(
        user_id=client_db["stu_user"].id,
        email=client_db["stu_user"].email,
        role="HOD",
    )
    r = c.post(
        f"/ufm-cases/{case['id']}/reviews",
        headers=_h(forged),
        json=_sign("FORWARD"),
    )
    assert r.status_code == 403
