"""AI detection alerts must target Invigilators only (not HOD)."""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from detection_bridge import notify_detection_alert
from models.audit_log import AuditLog  # noqa: F401
from models.base import Base
from models.camera import Camera  # noqa: F401
from models.case_review import CaseReview  # noqa: F401
from models.clarification import Clarification  # noqa: F401
from models.detection import Detection
from models.exam import Exam  # noqa: F401
from models.exam_enrollment import ExamEnrollment  # noqa: F401
from models.exam_invigilator import ExamInvigilator  # noqa: F401
from models.exam_room import ExamRoom  # noqa: F401
from models.evidence import Evidence  # noqa: F401
from models.notification import Notification
from models.result_control import ResultControl  # noqa: F401
from models.student import Student  # noqa: F401
from models.ufm_case import UfmCase  # noqa: F401
from models.user import User


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        inv = User(
            email="inv@test.com",
            name="Invigilator",
            role="INVIGILATOR",
            password_hash="x",
            is_active=True,
        )
        hod = User(
            email="hod@test.com",
            name="HOD",
            role="HOD",
            password_hash="x",
            is_active=True,
        )
        session.add_all([inv, hod])
        session.commit()
        yield session
    finally:
        session.close()


def test_confirmed_alert_goes_to_invigilator_not_hod(db):
    det = Detection(
        camera_id=None,
        student_id=None,
        detection_type="mobile_phone",
        confidence=0.91,
        timestamp=datetime.utcnow(),
        is_confirmed=True,
        model_version="coco/yolov8n.pt",
    )
    db.add(det)
    db.flush()

    n = notify_detection_alert(db, det, is_demo=False)
    db.commit()
    assert n == 1

    rows = db.scalars(select(Notification)).all()
    assert len(rows) == 1
    inv = db.scalars(select(User).where(User.role == "INVIGILATOR")).one()
    hod = db.scalars(select(User).where(User.role == "HOD")).one()
    assert rows[0].user_id == inv.id
    assert rows[0].user_id != hod.id
    assert rows[0].type == "DETECTION_ALERT"
    assert "detection confidence" in (rows[0].message or "").lower()
    assert "model=coco/yolov8n.pt" in (rows[0].message or "")
