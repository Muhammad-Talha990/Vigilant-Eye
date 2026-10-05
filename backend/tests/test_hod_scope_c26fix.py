"""
C26-FIX — HOD has no case creation, live monitoring, or detections.

Run from backend/:
  pytest -q tests/test_hod_scope_c26fix.py
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from case_access import DETECTION_STAFF_ROLES, MONITOR_ROLES
from database import get_db
from main import app
from models.base import Base
from models.user import User
from security import create_access_token, hash_password

ROOT = Path(__file__).resolve().parents[2]
FE = ROOT / "frontend" / "src"


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
    hod = User(
        name="Hod C26Fix",
        email="hod.c26fix@demo.com",
        password_hash=hash_password("UnusedPass1!"),
        role="HOD",
        is_active=True,
    )
    db.add(hod)
    db.commit()
    db.refresh(hod)

    def token(user: User) -> str:
        return create_access_token(
            user_id=user.id, email=user.email, role=user.role
        )

    client = TestClient(app)
    yield {"client": client, "token": token, "hod": hod}
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_role_sets_invigilator_only():
    assert MONITOR_ROLES == frozenset({"INVIGILATOR"})
    assert DETECTION_STAFF_ROLES == frozenset({"INVIGILATOR"})
    assert "HOD" not in MONITOR_ROLES
    assert "HOD" not in DETECTION_STAFF_ROLES


def test_hod_api_denied_monitor_detect_create(client_db):
    c = client_db["client"]
    h = {
        "Authorization": f"Bearer {client_db['token'](client_db['hod'])}"
    }
    assert c.get("/live/status", headers=h).status_code == 403
    assert c.get("/detections", headers=h).status_code == 403
    assert (
        c.post(
            "/ufm-cases",
            headers=h,
            json={
                "student_id": 1,
                "exam_id": 1,
                "violation_type": "MOBILE_PHONE",
                "description": "should fail",
                "signer_name": "Hod",
                "signature_ack": True,
            },
        ).status_code
        == 403
    )


def test_hod_frontend_has_no_create_or_monitor_actions():
    nav = (FE / "config" / "navByRole.js").read_text(encoding="utf-8")
    dash = (FE / "config" / "dashboardByRole.js").read_text(encoding="utf-8")
    role_access = (FE / "config" / "roleAccess.js").read_text(encoding="utf-8")

    hod_block = nav.split("HOD: [")[1].split("DEC: [")[0]
    assert "/app/monitoring" not in hod_block
    assert "/app/detections" not in hod_block
    assert "/app/cases/new" not in hod_block
    assert "Live Monitoring" not in hod_block
    assert "Report UFM" not in hod_block
    assert "Create UFM" not in hod_block
    assert "Report a Case" not in hod_block

    qa = dash.split("export function quickActionsForRole")[1]
    hod_qa = qa.split('if (role === "HOD")')[1].split('if (role === "DEC")')[0]
    assert "/app/monitoring" not in hod_qa
    assert "/app/detections" not in hod_qa
    assert "/app/cases/new" not in hod_qa
    assert "Create UFM" not in hod_qa
    assert "Report UFM" not in hod_qa
    assert "/app/cases?scope=active" in hod_qa
    assert "/app/cases?status=PENDING" not in hod_qa
    assert "/app/evidence" in hod_qa

    mon = role_access.split("MONITOR_ROLES")[1].split("DETECTION_ROLES")[0]
    det = role_access.split("DETECTION_ROLES")[1].split("REPORTS_ROLES")[0]
    create = role_access.split("CASE_CREATE_ROLES")[1].split(
        "EVIDENCE_UPLOAD_ROLES"
    )[0]
    assert "HOD" not in mon
    assert "HOD" not in det
    assert "HOD" not in create
    assert "INVIGILATOR" in mon
    assert "INVIGILATOR" in det
    assert "INVIGILATOR" in create

    deny = nav.split("HOD_NAV_DENY_PATHS")[1].split("function sanitizeNavForRole")[
        0
    ]
    assert '"/app/monitoring"' in deny
    assert '"/app/detections"' in deny
    assert '"/app/cases/new"' in deny
