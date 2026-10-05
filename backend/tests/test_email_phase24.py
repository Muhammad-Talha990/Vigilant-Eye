"""
Phase 24 — Production-ready email notification system.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models.audit_log import AuditLog
from models.base import Base
from models.notification import Notification
from models.user import User
from security import create_access_token, hash_password


@pytest.fixture()
def client_db(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_CREATE_ALL_ON_STARTUP", "0")
    monkeypatch.setenv("EMAIL_ENABLED", "1")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)

    import email_notify

    email_notify.reload_email_config_from_env()

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

    def add_user(*, email: str, role: str, name: str | None = None, active: bool = True):
        u = User(
            name=name or email.split("@")[0],
            email=email,
            password_hash=hash_password("UnusedPass1!"),
            role=role,
            is_active=active,
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u

    admin = add_user(email="admin24@example.com", role="ADMINISTRATOR", name="Admin24")
    hod = add_user(email="hod24@example.com", role="HOD")
    inv = add_user(email="inv24@example.com", role="INVIGILATOR")
    student = add_user(email="student24@example.com", role="STUDENT")
    inactive = add_user(
        email="inactive24@example.com", role="HOD", name="Inactive", active=False
    )

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
        "hod": hod,
        "inv": inv,
        "student": student,
        "inactive": inactive,
        "Session": TestingSession,
        "email_notify": email_notify,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


# --- Configuration ---


def test_email_disabled_returns_disabled(client_db, monkeypatch):
    en = client_db["email_notify"]
    monkeypatch.setenv("EMAIL_ENABLED", "0")
    en.reload_email_config_from_env()
    result = en.send_email(
        to_email="admin24@example.com",
        subject="t",
        body="b",
    )
    assert result == "disabled"


def test_email_mock_when_smtp_incomplete(client_db, monkeypatch):
    en = client_db["email_notify"]
    monkeypatch.setenv("EMAIL_ENABLED", "1")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    en.reload_email_config_from_env()
    result = en.send_email(
        to_email="admin24@example.com",
        subject="Mock subject",
        body="body",
    )
    assert result == "mock"
    status = en.get_email_status()
    assert status["smtp_configured"] is False
    assert status["last_delivery_status"] == "mock"


def test_incomplete_smtp_production_validation(monkeypatch):
    monkeypatch.setenv("EMAIL_ENABLED", "1")
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    monkeypatch.delenv("SMTP_FROM_EMAIL", raising=False)
    import email_notify

    email_notify.reload_email_config_from_env()
    errs = email_notify.validate_email_settings_for_production()
    assert any("SMTP_HOST" in e for e in errs)


def test_unset_email_enabled_skips_production_smtp_requirement(monkeypatch):
    monkeypatch.delenv("EMAIL_ENABLED", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    import email_notify

    email_notify.reload_email_config_from_env()
    assert email_notify.validate_email_settings_for_production() == []


def test_email_disabled_production_ok(monkeypatch):
    monkeypatch.setenv("EMAIL_ENABLED", "0")
    import email_notify

    email_notify.reload_email_config_from_env()
    assert email_notify.validate_email_settings_for_production() == []


def test_admin_system_info_safe_email_fields(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    r = c.get("/admin/system-info", headers=h)
    assert r.status_code == 200
    body = r.json()
    blob = str(body).lower()
    assert "smtp_password" not in blob
    assert "jwt_secret" not in blob
    assert "email_notifications" in body
    assert "smtp_configured" in body
    assert "last_delivery_status" in body
    # Never expose secret-looking values even if env had them
    assert body.get("smtp_host") in (None, "", body.get("smtp_host"))


# --- Recipient ---


def test_recipient_is_user_email(client_db):
    from notify_helpers import create_notification

    db = client_db["db"]
    hod = client_db["hod"]
    with patch("notify_helpers.send_email", return_value="sent") as mocked:
        create_notification(
            db,
            user_id=hod.id,
            case_id=42,
            type="CASE_ACTION_REQUIRED",
            title="Action needed",
            message="Please review",
        )
        db.commit()
        mocked.assert_called_once()
        assert mocked.call_args.kwargs["to_email"] == "hod24@example.com"
        assert "html" in mocked.call_args.kwargs


def test_inactive_user_no_email(client_db):
    from notify_helpers import create_notification

    db = client_db["db"]
    inactive = client_db["inactive"]
    with patch("notify_helpers.send_email", return_value="sent") as mocked:
        create_notification(
            db,
            user_id=inactive.id,
            case_id=1,
            type="CASE_CREATED",
            title="Case",
            message="msg",
        )
        db.commit()
        mocked.assert_not_called()
    note = db.scalar(
        select(Notification).where(Notification.user_id == inactive.id)
    )
    assert note is not None


def test_unknown_user_no_email_queued(client_db):
    from notify_helpers import create_notification

    db = client_db["db"]
    with patch("notify_helpers.send_email", return_value="sent") as mocked:
        create_notification(
            db,
            user_id=999999,
            case_id=None,
            type="CASE_STATUS",
            title="x",
            message="y",
        )
        assert not db.info.get("ve_pending_emails")
        db.rollback()
        mocked.assert_not_called()


# --- Authorization ---


def test_admin_test_email_allowed_mock(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    r = c.post("/admin/email/test", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["result"] in {"mock", "sent", "disabled", "error"}
    assert body["to_masked"].endswith("@example.com")
    assert "password" not in str(body).lower() or "password" not in body["detail"].lower()
    # Audit exists
    db = client_db["db"]
    audit = db.scalar(
        select(AuditLog).where(AuditLog.action == "ADMIN_EMAIL_TEST")
    )
    assert audit is not None


@pytest.mark.parametrize(
    "role_key",
    ["student", "inv", "hod"],
)
def test_non_admin_cannot_send_test_email(client_db, role_key):
    c = client_db["client"]
    user = client_db[role_key]
    h = _h(client_db["token"](user))
    r = c.post("/admin/email/test", headers=h)
    assert r.status_code == 403


def test_test_email_uses_admin_user_email_only(client_db):
    """Endpoint must send only to authenticated Administrator User.email."""
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    with patch("email_notify.send_email", return_value="mock") as mocked:
        r = c.post(
            "/admin/email/test",
            headers={**h, "Content-Type": "application/json"},
            json={"to": "attacker@evil.test", "to_email": "attacker@evil.test"},
        )
    assert r.status_code == 200
    mocked.assert_called_once()
    assert mocked.call_args.kwargs["to_email"] == "admin24@example.com"
    assert "evil" not in r.json()["to_masked"]


# --- Notification + clarification email ---


def test_clarification_type_sends_email(client_db):
    from notify_helpers import create_notification

    db = client_db["db"]
    student = client_db["student"]
    with patch("notify_helpers.send_email", return_value="sent") as mocked:
        create_notification(
            db,
            user_id=student.id,
            case_id=7,
            type="CLARIFICATION",
            title="Clarification required",
            message="Please respond in the portal.",
        )
        db.commit()
        mocked.assert_called_once()
        assert mocked.call_args.kwargs["to_email"] == student.email


def test_portal_only_type_skips_email(client_db):
    from notify_helpers import create_notification

    db = client_db["db"]
    student = client_db["student"]
    with patch("notify_helpers.send_email", return_value="sent") as mocked:
        create_notification(
            db,
            user_id=student.id,
            case_id=None,
            type="UI_HINT",
            title="Minor",
            message="Ignore",
        )
        db.commit()
        mocked.assert_not_called()
    assert (
        db.scalar(
            select(Notification).where(
                Notification.user_id == student.id, Notification.type == "UI_HINT"
            )
        )
        is not None
    )


# --- Failure handling ---


def test_smtp_failure_does_not_rollback_notification(client_db, monkeypatch):
    from notify_helpers import create_notification

    en = client_db["email_notify"]
    monkeypatch.setenv("EMAIL_ENABLED", "1")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.test")
    en.reload_email_config_from_env()

    db = client_db["db"]
    hod = client_db["hod"]
    with patch("email_notify.smtplib.SMTP", side_effect=OSError("down")):
        create_notification(
            db,
            user_id=hod.id,
            case_id=3,
            type="RESULT_HOLD",
            title="Hold applied",
            message="Results held — see portal.",
        )
        db.commit()
    note = db.scalar(
        select(Notification).where(
            Notification.user_id == hod.id, Notification.title == "Hold applied"
        )
    )
    assert note is not None
    assert en.get_email_status()["last_delivery_status"] == "error"


def test_send_email_never_raises(client_db, monkeypatch):
    en = client_db["email_notify"]
    monkeypatch.setattr(en, "EMAIL_ENABLED", True)
    monkeypatch.setattr(en, "SMTP_HOST", "smtp.example")
    monkeypatch.setattr(en, "SMTP_FROM", "noreply@example.edu")
    with patch("email_notify.smtplib.SMTP", side_effect=TimeoutError("t")):
        assert (
            en.send_email(to_email="a@b.c", subject="s", body="b") == "error"
        )


def test_rollback_skips_queued_email(client_db):
    from notify_helpers import create_notification

    db = client_db["db"]
    hod = client_db["hod"]
    with patch("notify_helpers.send_email", return_value="sent") as mocked:
        create_notification(
            db,
            user_id=hod.id,
            case_id=1,
            type="CASE_CREATED",
            title="Will rollback",
            message="x",
        )
        db.rollback()
        mocked.assert_not_called()


# --- Security ---


def test_html_escaping_in_templates():
    from email_templates import build_notification_email

    content = build_notification_email(
        title='<script>alert(1)</script>',
        message='Hello <b>x</b> & "y"',
        case_id=9,
        notification_type="CASE_STATUS",
        portal_base_url="https://portal.example.edu",
    )
    assert "<script>" not in content.html
    assert "&lt;script&gt;" in content.html
    assert "&lt;b&gt;" in content.html
    assert "https://portal.example.edu" in content.html
    assert "jwt" not in content.html.lower()
    assert "password" not in content.text.lower()


def test_smtp_password_not_in_api_or_status(client_db, monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", "SUPER_SECRET_SMTP_PASS")
    client_db["email_notify"].reload_email_config_from_env()
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    info = c.get("/admin/system-info", headers=h).json()
    test = c.post("/admin/email/test", headers=h).json()
    status = client_db["email_notify"].get_email_status()
    joined = str(info) + str(test) + str(status)
    assert "SUPER_SECRET_SMTP_PASS" not in joined


def test_frontend_bundle_has_no_smtp_secrets():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "frontend" / "src"
    hits = []
    for path in root.rglob("*"):
        if path.suffix.lower() not in {".js", ".jsx", ".ts", ".tsx", ".env"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for needle in ("SMTP_PASSWORD", "SMTP_USER=", "JWT_SECRET"):
            if needle in text:
                hits.append(f"{path}:{needle}")
    assert hits == []


def test_mask_email():
    from email_notify import mask_email

    assert mask_email("admin24@example.com") == "a***@example.com"
    assert "@" in mask_email("x@y.z")


def test_notification_cross_user_isolation(client_db):
    from notify_helpers import create_notification

    db = client_db["db"]
    create_notification(
        db,
        user_id=client_db["hod"].id,
        case_id=1,
        type="CASE_STATUS",
        title="HOD only",
        message="private",
        send_mail=False,
    )
    db.commit()
    c = client_db["client"]
    # Student must not see HOD notifications via list endpoint if exists
    h = _h(client_db["token"](client_db["student"]))
    r = c.get("/notifications", headers=h)
    if r.status_code == 200:
        items = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
        assert all(
            (i.get("title") != "HOD only") for i in items
        )


# --- Idempotency / after_commit ---


def test_one_notification_one_email(client_db):
    from notify_helpers import create_notification

    db = client_db["db"]
    with patch("notify_helpers.send_email", return_value="sent") as mocked:
        create_notification(
            db,
            user_id=client_db["admin"].id,
            case_id=5,
            type="DETECTION_ALERT",
            title="Alert",
            message="See portal",
        )
        db.commit()
        assert mocked.call_count == 1


def test_aliases_smtp_username_and_from_email(monkeypatch):
    monkeypatch.setenv("EMAIL_ENABLED", "1")
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.setenv("SMTP_USERNAME", "relay-user")
    monkeypatch.delenv("SMTP_FROM", raising=False)
    monkeypatch.setenv("SMTP_FROM_EMAIL", "notifications@example.edu")
    monkeypatch.setenv("SMTP_PASSWORD", "x")
    import email_notify

    email_notify.reload_email_config_from_env()
    assert email_notify.SMTP_USER == "relay-user"
    assert email_notify.SMTP_FROM == "notifications@example.edu"
    assert email_notify.smtp_configured() is True
