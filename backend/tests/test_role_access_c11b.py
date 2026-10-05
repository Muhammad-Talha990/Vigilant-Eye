"""
C11-B — focused role access / authorization boundaries.

Run from backend/:
  pytest -q tests/test_role_access_c11b.py
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

    room = ExamRoom(room_number="C11B-R1", building="Block A", capacity=40)
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

    admin = add_user(email="admin.c11b@demo.com", role="ADMINISTRATOR", name="Admin C11B")
    inv = add_user(email="inv.c11b@demo.com", role="INVIGILATOR", name="Inv C11B")
    hod = add_user(email="hod.c11b@demo.com", role="HOD", name="Hod C11B")
    dec = add_user(email="dec.c11b@demo.com", role="DEC", name="Dec C11B")
    exam = add_user(email="exam.c11b@demo.com", role="EXAM_DEPARTMENT", name="Exam C11B")
    ufm = add_user(email="ufm.c11b@demo.com", role="UFM_COMMITTEE", name="Ufm C11B")
    stu = add_user(email="stu.c11b@demo.com", role="STUDENT", name="Stu C11B")
    stu_b = add_user(email="stub.c11b@demo.com", role="STUDENT", name="StuB C11B")

    student = Student(
        student_id="C11BSTU01",
        name="C11B Student",
        department="CS",
        program="BSCS",
        user_id=stu.id,
    )
    student_b = Student(
        student_id="C11BSTU02",
        name="C11B Other",
        department="EE",
        program="BSEE",
        user_id=stu_b.id,
    )
    exam_row = Exam(
        course_code="C11B101",
        course_name="C11B Exam",
        semester="Fall",
        exam_date=date(2026, 10, 1),
        start_time=time(9, 0),
        end_time=time(12, 0),
        room_id=room.id,
    )
    cam = Camera(
        camera_id="CAM-C11B",
        name="C11B Cam",
        room_id=room.id,
        stream_url="webcam:0",
        is_active=True,
    )
    det = Detection(
        camera_id=None,
        detection_type="phone",
        confidence=0.91,
        is_confirmed=True,
        is_seen=False,
        is_demo=False,
    )
    db.add_all([student, student_b, exam_row, cam, det])
    db.commit()
    db.refresh(student)
    db.refresh(student_b)
    db.refresh(exam_row)
    db.refresh(cam)
    db.refresh(det)

    case = UfmCase(
        case_number="UFM-C11B-001",
        student_id=student.id,
        exam_id=exam_row.id,
        reported_by=inv.id,
        violation_type="MOBILE_PHONE",
        description="C11B boundary case",
        status="PENDING",
        signer_name="Inv C11B",
        signature_ack=True,
    )
    db.add(case)
    db.commit()
    db.refresh(case)

    def token(user: User) -> str:
        return create_access_token(
            user_id=user.id, email=user.email, role=user.role
        )

    client = TestClient(app)
    yield {
        "client": client,
        "db": db,
        "token": token,
        "admin": admin,
        "inv": inv,
        "hod": hod,
        "dec": dec,
        "exam": exam,
        "ufm": ufm,
        "stu": stu,
        "stu_b": stu_b,
        "student": student,
        "student_b": student_b,
        "exam_row": exam_row,
        "cam": cam,
        "det": det,
        "case": case,
    }
    app.dependency_overrides.clear()
    db.close()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def _sign(action="FORWARD", remarks="ok"):
    return {
        "action": action,
        "remarks": remarks,
        "signer_name": "Reviewer",
        "signature_ack": True,
    }


def _case_body(client_db, **extra):
    body = {
        "student_id": client_db["student"].id,
        "exam_id": client_db["exam_row"].id,
        "violation_type": "MOBILE_PHONE",
        "description": "C11B create attempt",
        "signer_name": "Creator",
        "signature_ack": True,
    }
    body.update(extra)
    return body


# --- ADMINISTRATOR ---


def test_admin_denied_operational_ufm(client_db):
    c, t, admin = client_db["client"], client_db["token"], client_db["admin"]
    h = _h(t(admin))
    listed = c.get("/ufm-cases", headers=h)
    assert listed.status_code == 200
    assert listed.json() == []
    assert c.post("/ufm-cases", headers=h, json=_case_body(client_db)).status_code == 403
    assert c.get("/detections", headers=h).status_code == 403
    assert c.get("/live/status", headers=h).status_code == 403
    assert c.get("/audit-logs", headers=h).status_code == 403
    assert c.get("/result-controls", headers=h).status_code == 403
    assert c.get("/ufm-cases/export.csv", headers=h).status_code == 403


def test_admin_audit_api_allowed(client_db):
    """Admin uses /admin/audit-logs (not operational /audit-logs)."""
    c, t, admin = client_db["client"], client_db["token"], client_db["admin"]
    h = _h(t(admin))
    r = c.get("/admin/audit-logs", headers=h)
    assert r.status_code == 200


# --- INVIGILATOR ---


def test_invigilator_monitoring_detections_create_evidence(client_db):
    c, t, inv = client_db["client"], client_db["token"], client_db["inv"]
    h = _h(t(inv))
    assert c.get("/live/status", headers=h).status_code == 200
    assert c.get("/detections", headers=h).status_code == 200
    created = c.post("/ufm-cases", headers=h, json=_case_body(client_db))
    assert created.status_code == 201, created.text


def test_invigilator_denied_audit_results_staff(client_db):
    c, t, inv = client_db["client"], client_db["token"], client_db["inv"]
    h = _h(t(inv))
    # C27: Invigilator may export own-case CSV via REPORTS_ROLES
    assert c.get("/ufm-cases/export.csv", headers=h).status_code == 200
    assert c.get("/audit-logs", headers=h).status_code == 403
    assert c.get("/result-controls", headers=h).status_code == 403
    # Staff provisioning: cannot create INVIGILATOR/staff via operational /users
    r = c.post(
        "/users",
        headers=h,
        json={
            "name": "Staff",
            "email": "staff.inv.c11b@demo.com",
            "password": "Demo@12345",
            "role": "INVIGILATOR",
        },
    )
    assert r.status_code == 403
    # Cannot create student master records
    r2 = c.post(
        "/students",
        headers=h,
        json={
            "student_id": "C11BINV99",
            "name": "Should Fail",
            "department": "CS",
            "program": "BSCS",
        },
    )
    assert r2.status_code == 403


# --- HOD ---


def test_hod_review_allowed_monitor_create_denied(client_db):
    c, t = client_db["client"], client_db["token"]
    h = _h(t(client_db["hod"]))
    # C26-FIX: HOD is case review only — no live monitoring / detections / create
    assert c.get("/live/status", headers=h).status_code == 403
    assert c.get("/detections", headers=h).status_code == 403
    assert (
        c.post("/ufm-cases", headers=h, json=_case_body(client_db)).status_code
        == 403
    )
    assert c.get("/audit-logs", headers=h).status_code == 200
    assert c.get("/ufm-cases/export.csv", headers=h).status_code == 200
    # Forward PENDING → DEC_REVIEW
    case_id = client_db["case"].id
    fwd = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=h,
        json=_sign("FORWARD", "verified"),
    )
    assert fwd.status_code == 201, fwd.text
    # Result release denied
    assert c.get("/result-controls", headers=h).status_code == 403
    # Staff role create denied
    r = c.post(
        "/users",
        headers=h,
        json={
            "name": "Staff",
            "email": "staff.hod.c11b@demo.com",
            "password": "Demo@12345",
            "role": "INVIGILATOR",
        },
    )
    assert r.status_code == 403


# --- DEC ---


def test_dec_review_allowed_monitor_detection_create_denied(client_db):
    c, t = client_db["client"], client_db["token"]
    # Drive case to DEC_REVIEW first
    hod_h = _h(t(client_db["hod"]))
    case_id = client_db["case"].id
    assert (
        c.post(
            f"/ufm-cases/{case_id}/reviews",
            headers=hod_h,
            json=_sign("FORWARD"),
        ).status_code
        == 201
    )

    h = _h(t(client_db["dec"]))
    assert c.get("/ufm-cases", headers=h).status_code == 200
    assert c.get("/live/status", headers=h).status_code == 403
    assert c.get("/detections", headers=h).status_code == 403
    assert (
        c.post("/ufm-cases", headers=h, json=_case_body(client_db)).status_code
        == 403
    )
    assert c.get("/result-controls", headers=h).status_code == 403
    fwd = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=h,
        json=_sign("FORWARD", "to exam"),
    )
    assert fwd.status_code == 201, fwd.text


# --- EXAM DEPARTMENT ---


def test_exam_department_ops_allowed_monitor_create_denied(client_db):
    c, t = client_db["client"], client_db["token"]
    case_id = client_db["case"].id
    for user, action in (
        (client_db["hod"], "FORWARD"),
        (client_db["dec"], "FORWARD"),
    ):
        r = c.post(
            f"/ufm-cases/{case_id}/reviews",
            headers=_h(t(user)),
            json=_sign(action),
        )
        assert r.status_code == 201, r.text

    h = _h(t(client_db["exam"]))
    # C26: Exam Department is case-processing — not live surveillance
    assert c.get("/live/status", headers=h).status_code == 403
    assert c.get("/detections", headers=h).status_code == 403
    assert (
        c.post("/ufm-cases", headers=h, json=_case_body(client_db)).status_code
        == 403
    )
    assert c.get("/ufm-cases/export.csv", headers=h).status_code == 200
    assert c.get("/result-controls", headers=h).status_code == 200
    # Final APPROVE only valid for UFM_COMMITTEE at UFM_COMMITTEE_REVIEW
    deny = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=h,
        json=_sign("APPROVE", "not allowed"),
    )
    assert deny.status_code in (400, 403, 422)
    fwd = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=h,
        json=_sign("FORWARD", "to committee"),
    )
    assert fwd.status_code == 201, fwd.text


# --- UFM COMMITTEE ---


def test_ufm_final_review_allowed_monitor_create_denied(client_db):
    c, t = client_db["client"], client_db["token"]
    case_id = client_db["case"].id
    for user, action in (
        (client_db["hod"], "FORWARD"),
        (client_db["dec"], "FORWARD"),
        (client_db["exam"], "FORWARD"),
    ):
        r = c.post(
            f"/ufm-cases/{case_id}/reviews",
            headers=_h(t(user)),
            json=_sign(action),
        )
        assert r.status_code == 201, r.text

    h = _h(t(client_db["ufm"]))
    assert c.get("/live/status", headers=h).status_code == 403
    assert c.get("/detections", headers=h).status_code == 403
    assert (
        c.post("/ufm-cases", headers=h, json=_case_body(client_db)).status_code
        == 403
    )
    assert c.get("/result-controls", headers=h).status_code == 200
    ok = c.post(
        f"/ufm-cases/{case_id}/reviews",
        headers=h,
        json=_sign("APPROVE", "sustained"),
    )
    assert ok.status_code == 201, ok.text
    # Staff create denied
    r = c.post(
        "/users",
        headers=h,
        json={
            "name": "Staff",
            "email": "staff.ufm.c11b@demo.com",
            "password": "Demo@12345",
            "role": "STUDENT",
        },
    )
    assert r.status_code == 403


# --- STUDENT ---


def test_student_own_cases_only_and_ops_denied(client_db):
    c, t = client_db["client"], client_db["token"]
    h = _h(t(client_db["stu"]))
    listed = c.get("/ufm-cases", headers=h)
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()}
    assert client_db["case"].id in ids

    other = UfmCase(
        case_number="UFM-C11B-OTHER",
        student_id=client_db["student_b"].id,
        exam_id=client_db["exam_row"].id,
        reported_by=client_db["inv"].id,
        violation_type="OTHER",
        description="Other student",
        status="PENDING",
        signer_name="Inv C11B",
        signature_ack=True,
    )
    client_db["db"].add(other)
    client_db["db"].commit()
    client_db["db"].refresh(other)

    listed2 = c.get("/ufm-cases", headers=h)
    assert listed2.status_code == 200
    ids2 = {row["id"] for row in listed2.json()}
    assert other.id not in ids2

    assert c.get(f"/ufm-cases/{other.id}", headers=h).status_code == 403
    assert c.get("/detections", headers=h).status_code == 403
    assert c.get("/live/status", headers=h).status_code == 403
    assert c.get("/audit-logs", headers=h).status_code == 403
    assert c.get("/result-controls", headers=h).status_code == 403
    assert c.get("/ufm-cases/export.csv", headers=h).status_code == 403
    assert c.get("/students", headers=h).status_code == 403


def test_frontend_nav_admin_audit_path_and_no_ops_users(client_db):
    """Static nav/route source checks (complements route gates)."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "frontend" / "src"
    nav = (root / "config" / "navByRole.js").read_text(encoding="utf-8")
    app_jsx = (root / "App.jsx").read_text(encoding="utf-8")
    dash = (root / "config" / "dashboardByRole.js").read_text(encoding="utf-8")

    assert "/app/admin/audit" in nav
    assert '"/app/audit"' not in nav.split("ADMINISTRATOR:")[1].split("INVIGILATOR:")[0]
    assert "/app/admin/audit" in dash
    assert "to: \"/app/audit\"" not in dash.split("ADMINISTRATOR")[1].split("INVIGILATOR")[0]

    # Administrator: Notifications under Communication; Profile under Account
    admin_block = nav.split("ADMINISTRATOR: [")[1].split("INVIGILATOR: [")[0]
    assert 'section: "Communication"' in admin_block
    assert "/app/notifications" in admin_block
    assert "/app/admin/profile" in admin_block
    # Notifications must not sit in the Account group with Profile
    account_slice = admin_block.split('section: "Account"')[1]
    assert "/app/notifications" not in account_slice
    assert "/app/admin/profile" in account_slice
    comm_slice = admin_block.split('section: "Communication"')[1].split(
        'section: "Account"'
    )[0]
    assert "/app/notifications" in comm_slice
    assert "/app/admin/profile" not in comm_slice

    # Operational Users page removed; /app/users redirects
    assert 'from "./pages/UsersPage"' not in app_jsx
    assert 'path="users"' in app_jsx
    assert "Navigate to=\"/app/dashboard\"" in app_jsx or 'to="/app/dashboard"' in app_jsx

    # DEC nav must not expose detections / monitoring
    dec_block = nav.split("DEC: [")[1].split("EXAM_DEPARTMENT: [")[0]
    assert "/app/detections" not in dec_block
    assert "/app/monitoring" not in dec_block

    # Invigilator must not see audit / results / students / exam setup
    inv_block = nav.split("INVIGILATOR: [")[1].split("HOD: [")[0]
    assert "/app/audit" not in inv_block
    assert "/app/result-controls" not in inv_block
    assert "/app/students" not in inv_block
    assert "/app/master-data" not in inv_block
    assert "Exam Setup" not in inv_block
    assert "Exam Catalog" not in inv_block
    assert "Administration" not in inv_block
    assert "Students" not in inv_block
    # Required Invigilator modules remain (C27: Reports allowed for own cases)
    assert "/app/monitoring" in inv_block
    assert "/app/detections" in inv_block
    assert "/app/cases/new" in inv_block
    assert "/app/evidence" in inv_block
    assert "/app/notifications" in inv_block
    assert "/app/reports" in inv_block
    # Defense-in-depth sanitizer must remain (Windows Docker Vite stale-cache regression)
    assert "INVIGILATOR_NAV_DENY_PATHS" in nav
    assert "sanitizeNavForRole" in nav
    inv_deny = nav.split("INVIGILATOR_NAV_DENY_PATHS")[1].split(
        "function sanitizeNavForRole"
    )[0]
    assert '"/app/master-data"' in inv_deny
    assert '"/app/students"' in inv_deny
    assert '"/app/reports"' not in inv_deny

    # App route gates must exclude Invigilator from those three modules
    assert "STUDENT_DIRECTORY_VIEW_ROLES" in app_jsx
    assert "MASTER_DATA_VIEW_ROLES" in app_jsx
    assert "REPORTS_ROLES" in app_jsx
    assert 'path="students"' in app_jsx
    assert 'path="master-data"' in app_jsx
    assert 'path="reports"' in app_jsx

    role_access = (root / "config" / "roleAccess.js").read_text(encoding="utf-8")
    # Page gates: Invigilator removed from Students + Master Data modules
    md_block = role_access.split("MASTER_DATA_VIEW_ROLES")[1].split(
        "MASTER_DATA_CREATE_ROLES"
    )[0]
    assert "INVIGILATOR" not in md_block
    stu_block = role_access.split("STUDENT_DIRECTORY_VIEW_ROLES")[1].split(
        "STUDENT_DIRECTORY_MANAGE_ROLES"
    )[0]
    assert "INVIGILATOR" not in stu_block
    # C27: Reports includes Invigilator (separate from MONITOR/DETECTION/CREATE)
    rep_block = role_access.split("REPORTS_ROLES")[1].split("OPERATIONAL_AUDIT_ROLES")[
        0
    ]
    assert "INVIGILATOR" in rep_block
    assert "HOD" in rep_block
    # Invigilator quick actions must not point at removed modules
    inv_actions = (
        dash.split("export function quickActionsForRole")[1]
        .split('if (role === "INVIGILATOR")')[1]
        .split('if (role === "HOD")')[0]
    )
    assert "/app/students" not in inv_actions
    assert "/app/master-data" not in inv_actions
    assert "/app/reports" in inv_actions

    # HOD: case review only — no monitoring / detections / create (C26-FIX)
    hod_block = nav.split("HOD: [")[1].split("DEC: [")[0]
    assert "/app/master-data" not in hod_block
    assert "/app/students" not in hod_block
    assert "Exam Setup" not in hod_block
    assert "With DEC" not in hod_block
    assert "status=DEC_REVIEW" not in hod_block
    assert "/app/monitoring" not in hod_block
    assert "/app/detections" not in hod_block
    assert "/app/cases/new" not in hod_block
    assert "Live Monitoring" not in hod_block
    assert "Report UFM" not in hod_block
    assert "Create UFM" not in hod_block
    assert "/app/reports" in hod_block
    assert "/app/audit" in hod_block
    assert "/app/cases?scope=active" in hod_block
    assert "/app/cases?status=PENDING" not in hod_block
    assert "/app/cases" in hod_block
    assert "/app/evidence" in hod_block
    assert "UFM Review" in hod_block
    assert "HOD_NAV_DENY_PATHS" in nav
    hod_deny = nav.split("HOD_NAV_DENY_PATHS")[1].split(
        "function sanitizeNavForRole"
    )[0]
    assert '"/app/cases?status=DEC_REVIEW"' in hod_deny
    assert '"/app/cases/new"' in hod_deny
    assert '"/app/monitoring"' in hod_deny
    assert '"/app/detections"' in hod_deny

    # Page gates: HOD removed from Students + Master Data role arrays
    assert '"HOD"' not in md_block
    assert '"HOD"' not in stu_block
    md_create = role_access.split("MASTER_DATA_CREATE_ROLES")[1].split(
        "STUDENT_DIRECTORY_VIEW_ROLES"
    )[0]
    assert '"HOD"' not in md_create
    stu_manage = role_access.split("STUDENT_DIRECTORY_MANAGE_ROLES")[1].split(
        "export function roleIn"
    )[0]
    assert '"HOD"' not in stu_manage

    hod_actions = (
        dash.split("export function quickActionsForRole")[1]
        .split('if (role === "HOD")')[1]
        .split('if (role === "DEC")')[0]
    )
    assert "/app/students" not in hod_actions
    assert "/app/master-data" not in hod_actions
    assert "DEC_REVIEW" not in hod_actions
    assert "With DEC" not in hod_actions
    assert "/app/cases/new" not in hod_actions
    assert "Create UFM" not in hod_actions
    assert "Report UFM" not in hod_actions
    assert "/app/monitoring" not in hod_actions
    assert "/app/detections" not in hod_actions
    assert "/app/reports" in hod_actions
    assert "/app/audit" in hod_actions
    assert "/app/evidence" in hod_actions
    assert "/app/cases?scope=active" in hod_actions
    assert "/app/cases?status=PENDING" not in hod_actions

    # DEC must not see Students / Forwarded to Exam Dept. shortcuts
    dec_block = nav.split("DEC: [")[1].split("EXAM_DEPARTMENT: [")[0]
    assert "/app/students" not in dec_block
    assert "Students" not in dec_block
    assert "Forwarded to Exam Dept." not in dec_block
    assert "status=EXAM_DEPARTMENT_REVIEW" not in dec_block
    assert "/app/cases?status=DEC_REVIEW" in dec_block
    assert "/app/cases" in dec_block
    assert "/app/evidence" in dec_block
    assert "/app/reports" in dec_block
    assert "/app/audit" in dec_block
    assert "UFM Review" in dec_block
    assert "DEC_NAV_DENY_PATHS" in nav
    assert '"/app/students"' in nav.split("DEC_NAV_DENY_PATHS")[1].split(
        "function sanitizeNavForRole"
    )[0]
    assert '"/app/cases?status=EXAM_DEPARTMENT_REVIEW"' in nav.split(
        "DEC_NAV_DENY_PATHS"
    )[1].split("function sanitizeNavForRole")[0]
    assert '"DEC"' not in stu_block

    dec_actions = (
        dash.split("export function quickActionsForRole")[1]
        .split('if (role === "DEC")')[1]
        .split('if (role === "EXAM_DEPARTMENT")')[0]
    )
    assert "/app/students" not in dec_actions
    assert "EXAM_DEPARTMENT_REVIEW" not in dec_actions
    assert "Forwarded to Exam Dept." not in dec_actions
    assert "/app/cases?status=DEC_REVIEW" in dec_actions
    assert "/app/reports" in dec_actions
    assert "/app/audit" in dec_actions

    # Exam Department: case processing / holds — no live monitoring (C26)
    exam_block = nav.split("EXAM_DEPARTMENT: [")[1].split("UFM_COMMITTEE: [")[0]
    assert "/app/students" not in exam_block
    assert "/app/master-data" not in exam_block
    assert "Students" not in exam_block
    assert "Exam Setup" not in exam_block
    assert "/app/monitoring" not in exam_block
    assert "/app/detections" not in exam_block
    assert "/app/cases/new" not in exam_block
    assert "Case Processing" in exam_block
    assert "/app/cases?status=EXAM_DEPARTMENT_REVIEW" in exam_block
    assert "/app/result-controls" in exam_block
    assert "/app/reports" in exam_block
    assert "/app/audit" in exam_block
    assert "EXAM_DEPARTMENT_NAV_DENY_PATHS" in nav
    exam_deny = nav.split("EXAM_DEPARTMENT_NAV_DENY_PATHS")[1].split(
        "function sanitizeNavForRole"
    )[0]
    assert '"/app/students"' in exam_deny
    assert '"/app/master-data"' in exam_deny
    assert '"/app/monitoring"' in exam_deny
    assert '"/app/detections"' in exam_deny
    assert '"/app/cases/new"' in exam_deny
    assert '"EXAM_DEPARTMENT"' not in md_block
    assert '"EXAM_DEPARTMENT"' not in stu_block
    assert '"EXAM_DEPARTMENT"' not in md_create
    assert '"EXAM_DEPARTMENT"' not in stu_manage

    exam_actions = (
        dash.split("export function quickActionsForRole")[1]
        .split('if (role === "EXAM_DEPARTMENT")')[1]
        .split('if (role === "UFM_COMMITTEE")')[0]
    )
    assert "/app/students" not in exam_actions
    assert "/app/master-data" not in exam_actions
    assert "/app/monitoring" not in exam_actions
    assert "/app/detections" not in exam_actions
    assert "/app/cases/new" not in exam_actions
    assert "Exam Setup" not in exam_actions
    assert "/app/result-controls" in exam_actions
    assert "/app/reports" in exam_actions
    assert "/app/audit" in exam_actions

    # FE roleAccess: monitor / detect / create are Invigilator-only (C26-FIX)
    mon_block = role_access.split("MONITOR_ROLES")[1].split("DETECTION_ROLES")[0]
    det_block = role_access.split("DETECTION_ROLES")[1].split("REPORTS_ROLES")[0]
    assert "INVIGILATOR" in mon_block
    assert "HOD" not in mon_block
    assert "EXAM_DEPARTMENT" not in mon_block
    assert "INVIGILATOR" in det_block
    assert "HOD" not in det_block
    assert "EXAM_DEPARTMENT" not in det_block
    create_block = role_access.split("CASE_CREATE_ROLES")[1].split(
        "EVIDENCE_UPLOAD_ROLES"
    )[0]
    assert "INVIGILATOR" in create_block
    assert "HOD" not in create_block
    assert "EXAM_DEPARTMENT" not in create_block

    # UFM Committee must not see Students / monitoring / create case
    ufm_block = nav.split("UFM_COMMITTEE: [")[1].split("STUDENT: [")[0]
    assert "/app/students" not in ufm_block
    assert "Students" not in ufm_block
    assert "/app/monitoring" not in ufm_block
    assert "/app/detections" not in ufm_block
    assert "/app/cases/new" not in ufm_block
    assert "/app/cases?status=UFM_COMMITTEE_REVIEW" in ufm_block
    assert "/app/cases?status=APPROVED" in ufm_block
    assert "/app/cases?status=REJECTED" in ufm_block
    assert "/app/result-controls" in ufm_block
    assert "/app/evidence" in ufm_block
    assert "/app/reports" in ufm_block
    assert "/app/audit" in ufm_block
    assert "UFM_COMMITTEE_NAV_DENY_PATHS" in nav
    ufm_deny = nav.split("UFM_COMMITTEE_NAV_DENY_PATHS")[1].split(
        "function sanitizeNavForRole"
    )[0]
    assert '"/app/students"' in ufm_deny
    assert '"/app/monitoring"' in ufm_deny
    assert '"/app/detections"' in ufm_deny
    assert '"/app/cases/new"' in ufm_deny
    assert '"UFM_COMMITTEE"' not in stu_block

    ufm_actions = (
        dash.split("export function quickActionsForRole")[1]
        .split('if (role === "UFM_COMMITTEE")')[1]
        .split("return [")[1]
        .split("];")[0]
    )
    assert "/app/students" not in ufm_actions
    assert "/app/monitoring" not in ufm_actions
    assert "/app/cases/new" not in ufm_actions
    assert "/app/cases?status=UFM_COMMITTEE_REVIEW" in ufm_actions
    assert "/app/result-controls" in ufm_actions
    assert "/app/audit" in ufm_actions

    # Notification destinations must not send unauthorized roles to detections/holds
    from pathlib import Path as _P

    notif = (
        _P(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "config"
        / "notificationPresentation.js"
    ).read_text(encoding="utf-8")
    assert "DETECTION_ROLES" in notif
    assert "RESULT_CONTROL_ROLES" in notif
    assert "roleIn(role, DETECTION_ROLES)" in notif
    assert "roleIn(role, RESULT_CONTROL_ROLES)" in notif


def test_notification_destination_helpers_align_with_c11b():
    """Import the same role sets used by FE destination logic (documented contract)."""
    from case_access import DETECTION_STAFF_ROLES, MONITOR_ROLES

    assert DETECTION_STAFF_ROLES == MONITOR_ROLES
    assert MONITOR_ROLES == frozenset({"INVIGILATOR"})
    assert "HOD" not in DETECTION_STAFF_ROLES
    assert "DEC" not in DETECTION_STAFF_ROLES
    assert "EXAM_DEPARTMENT" not in DETECTION_STAFF_ROLES
    assert "UFM_COMMITTEE" not in DETECTION_STAFF_ROLES
    assert "ADMINISTRATOR" not in DETECTION_STAFF_ROLES
    assert "STUDENT" not in DETECTION_STAFF_ROLES
