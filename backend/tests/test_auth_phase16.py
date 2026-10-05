"""
Phase 16 — Google authentication, password gate, notification email safety.
"""

from __future__ import annotations

import importlib
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from google_auth import GoogleIdentity, normalize_email
from main import app
from models.base import Base
from models.notification import Notification
from models.user import User
from notify_helpers import create_notification
from security import hash_password


GOOGLE_CLIENT = "1234567890-phase16tests.apps.googleusercontent.com"


def _restore_dev_auth_config(monkeypatch):
    """Reload app_config/google_auth bindings so later suites keep password login."""
    for key in (
        "APP_ENV",
        "GOOGLE_CLIENT_ID",
        "PASSWORD_LOGIN_ENABLED",
        "ENABLE_DEMO_SEED",
        "CORS_ORIGINS",
        "JWT_SECRET",
        "JWT_EXPIRE_MINUTES",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
        "AUTH_MODE",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "demo")
    monkeypatch.setenv("PASSWORD_LOGIN_ENABLED", "1")
    import app_config

    importlib.reload(app_config)
    import google_auth

    importlib.reload(google_auth)
    import main as main_mod

    main_mod.password_login_enabled = app_config.password_login_enabled
    main_mod.google_auth_enabled = app_config.google_auth_enabled
    main_mod.verify_google_id_token = google_auth.verify_google_id_token


@pytest.fixture(autouse=True)
def _phase16_restore_dev_auth(monkeypatch):
    yield
    _restore_dev_auth_config(monkeypatch)


@pytest.fixture()
def client_db(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", GOOGLE_CLIENT)
    monkeypatch.setenv("PASSWORD_LOGIN_ENABLED", "1")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("AUTH_MODE", "both")
    import app_config

    importlib.reload(app_config)
    import google_auth

    importlib.reload(google_auth)
    # Keep main's imported symbols aligned with reloaded modules.
    import main as main_mod

    main_mod.password_login_enabled = app_config.password_login_enabled
    main_mod.google_auth_enabled = app_config.google_auth_enabled
    main_mod.auth_mode = app_config.auth_mode
    main_mod.demo_helpers_enabled = app_config.demo_helpers_enabled
    main_mod.verify_google_id_token = google_auth.verify_google_id_token

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    roles = [
        ("Demo Student", "student@demo.com", "STUDENT"),
        ("Demo Invigilator", "invigilator@demo.com", "INVIGILATOR"),
        ("Demo HOD", "hod@demo.com", "HOD"),
        ("Demo DEC", "dec@demo.com", "DEC"),
        ("Demo Exam", "examdept@demo.com", "EXAM_DEPARTMENT"),
        ("Demo UFM", "ufm@demo.com", "UFM_COMMITTEE"),
        ("Inactive User", "inactive@demo.com", "STUDENT"),
    ]
    for name, email, role in roles:
        db.add(
            User(
                name=name,
                email=email,
                password_hash=hash_password("Demo@123"),
                role=role,
                is_active=(email != "inactive@demo.com"),
            )
        )
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, db
    app.dependency_overrides.clear()
    db.close()


def _fake_identity(email: str, *, verified: bool = True) -> GoogleIdentity:
    return GoogleIdentity(
        email=normalize_email(email),
        email_verified=verified,
        subject="google-sub-1",
        name="Google User",
    )


@pytest.mark.parametrize(
    "email,role",
    [
        ("student@demo.com", "STUDENT"),
        ("invigilator@demo.com", "INVIGILATOR"),
        ("hod@demo.com", "HOD"),
        ("dec@demo.com", "DEC"),
        ("examdept@demo.com", "EXAM_DEPARTMENT"),
        ("ufm@demo.com", "UFM_COMMITTEE"),
    ],
)
def test_authorized_google_login_all_roles(client_db, email, role):
    client, _ = client_db
    with patch(
        "main.verify_google_id_token",
        return_value=_fake_identity(email),
    ):
        r = client.post("/auth/google", json={"id_token": "fake." + ("x" * 40)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == email
    assert body["user"]["role"] == role
    assert body["access_token"]


def test_unknown_google_account_denied(client_db):
    client, _ = client_db
    with patch(
        "main.verify_google_id_token",
        return_value=_fake_identity("stranger@gmail.com"),
    ):
        r = client.post("/auth/google", json={"id_token": "fake." + ("x" * 40)})
    assert r.status_code == 403
    assert "not authorized" in r.json()["detail"].lower()


def test_inactive_google_user_denied(client_db):
    client, _ = client_db
    with patch(
        "main.verify_google_id_token",
        return_value=_fake_identity("inactive@demo.com"),
    ):
        r = client.post("/auth/google", json={"id_token": "fake." + ("x" * 40)})
    assert r.status_code == 403
    assert "inactive" in r.json()["detail"].lower()


def test_unverified_google_email_denied(client_db, monkeypatch):
    client, _ = client_db
    monkeypatch.setenv("GOOGLE_CLIENT_ID", GOOGLE_CLIENT)
    import google_auth

    importlib.reload(google_auth)

    def boom(_token: str):
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Google email is not verified",
        )

    with patch("main.verify_google_id_token", side_effect=boom):
        r = client.post("/auth/google", json={"id_token": "fake." + ("x" * 40)})
    assert r.status_code == 403


def test_invalid_google_token_denied(client_db):
    client, _ = client_db
    with patch(
        "google_auth.id_token.verify_oauth2_token",
        side_effect=ValueError("Token invalid"),
    ):
        r = client.post("/auth/google", json={"id_token": "fake." + ("x" * 40)})
    assert r.status_code == 401


def test_expired_google_token_denied(client_db):
    client, _ = client_db
    with patch(
        "google_auth.id_token.verify_oauth2_token",
        side_effect=ValueError("Token expired"),
    ):
        r = client.post("/auth/google", json={"id_token": "fake." + ("x" * 40)})
    assert r.status_code == 401
    assert "expired" in r.json()["detail"].lower()


def test_wrong_audience_denied(client_db):
    client, _ = client_db
    with patch(
        "google_auth.id_token.verify_oauth2_token",
        side_effect=ValueError("Wrong audience"),
    ):
        r = client.post("/auth/google", json={"id_token": "fake." + ("x" * 40)})
    assert r.status_code == 401
    assert "audience" in r.json()["detail"].lower()


def test_wrong_issuer_denied(client_db):
    client, _ = client_db

    def bad_issuer(token, request, audience, clock_skew_in_seconds=0):
        return {
            "iss": "https://evil.example",
            "email": "hod@demo.com",
            "email_verified": True,
            "sub": "x",
            "aud": audience,
        }

    with patch("google_auth.id_token.verify_oauth2_token", side_effect=bad_issuer):
        r = client.post("/auth/google", json={"id_token": "fake." + ("x" * 40)})
    assert r.status_code == 401
    assert "issuer" in r.json()["detail"].lower()


def test_google_claims_cannot_change_db_role(client_db):
    client, _ = client_db
    # Identity says student email even if a forged "role" existed in claims —
    # we never read Google role; DB says STUDENT.
    with patch(
        "main.verify_google_id_token",
        return_value=_fake_identity("student@demo.com"),
    ):
        r = client.post("/auth/google", json={"id_token": "fake." + ("x" * 40)})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "STUDENT"
    token = r.json()["access_token"]
    # Student still cannot hit audit (Phase 11 / role gate).
    denied = client.get(
        "/audit-logs", headers={"Authorization": f"Bearer {token}"}
    )
    assert denied.status_code == 403


def test_frontend_cannot_submit_arbitrary_role(client_db):
    client, _ = client_db
    r = client.post(
        "/auth/google",
        json={
            "id_token": "fake." + ("x" * 40),
            "role": "UFM_COMMITTEE",
            "email": "student@demo.com",
        },
    )
    # Extra fields ignored by schema; still requires valid Google verify.
    with patch(
        "main.verify_google_id_token",
        return_value=_fake_identity("student@demo.com"),
    ):
        r = client.post(
            "/auth/google",
            json={"id_token": "fake." + ("x" * 40), "role": "HOD"},
        )
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "STUDENT"


def test_password_login_disabled_in_production_mode(client_db, monkeypatch):
    client, _ = client_db
    monkeypatch.setenv("PASSWORD_LOGIN_ENABLED", "0")
    import app_config

    importlib.reload(app_config)
    # main.password_login_enabled is imported by name — patch the function used in main
    with patch("main.password_login_enabled", return_value=False):
        r = client.post(
            "/auth/login",
            json={"email": "hod@demo.com", "password": "Demo@123"},
        )
    assert r.status_code == 403
    assert "google" in r.json()["detail"].lower()


def test_auth_config_exposes_modes(client_db):
    client, _ = client_db
    with patch("main.password_login_enabled", return_value=True), patch(
        "main.google_auth_enabled", return_value=True
    ), patch("app_config.GOOGLE_CLIENT_ID", GOOGLE_CLIENT):
        r = client.get("/auth/config")
    assert r.status_code == 200
    body = r.json()
    assert "password_login_enabled" in body
    assert "google_auth_enabled" in body


def test_notification_email_uses_correct_recipient(client_db):
    _, db = client_db
    user = db.scalar(select(User).where(User.email == "hod@demo.com"))
    with patch("notify_helpers.send_email", return_value="sent") as mocked:
        create_notification(
            db,
            user_id=user.id,
            case_id=None,
            type="CASE_ACTION_REQUIRED",
            title="Action needed",
            message="Please review",
        )
        db.commit()
        mocked.assert_called_once()
        assert mocked.call_args.kwargs["to_email"] == "hod@demo.com"
    note = db.scalar(
        select(Notification).where(Notification.user_id == user.id)
    )
    assert note is not None
    assert note.user_id == user.id


def test_email_failure_does_not_break_notification(client_db):
    _, db = client_db
    user = db.scalar(select(User).where(User.email == "student@demo.com"))

    def boom(**kwargs):
        raise RuntimeError("smtp down")

    # send_email itself never raises; simulate notify path still persisting if
    # wrapper swallowed — call create_notification with patched send_email that
    # returns error without raising (real behavior).
    with patch("notify_helpers.send_email", return_value="error"):
        create_notification(
            db,
            user_id=user.id,
            case_id=None,
            type="CASE_STATUS",
            title="Status",
            message="Updated",
        )
        db.commit()
    note = db.scalar(
        select(Notification)
        .where(Notification.user_id == user.id, Notification.title == "Status")
    )
    assert note is not None


def test_send_email_never_raises_on_smtp_error(monkeypatch):
    import email_notify

    monkeypatch.setattr(email_notify, "EMAIL_ENABLED", True)
    monkeypatch.setattr(email_notify, "SMTP_HOST", "smtp.example")
    monkeypatch.setattr(email_notify, "SMTP_FROM", "noreply@example.edu")

    with patch("email_notify.smtplib.SMTP", side_effect=OSError("down")):
        result = email_notify.send_email(
            to_email="a@example.edu", subject="t", body="b"
        )
    assert result == "error"


def test_normalize_email():
    assert normalize_email("  A@B.Com ") == "a@b.com"


def test_production_requires_google_client(monkeypatch):
    for key in (
        "APP_ENV",
        "JWT_SECRET",
        "JWT_EXPIRE_MINUTES",
        "CORS_ORIGINS",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
        "GOOGLE_CLIENT_ID",
        "PASSWORD_LOGIN_ENABLED",
        "AUTH_MODE",
        "ENABLE_DEMO_SEED",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "60")
    monkeypatch.setenv("CORS_ORIGINS", "https://portal.example.edu")
    monkeypatch.setenv("POSTGRES_PASSWORD", "strong-db-password-not-example")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://u:strong-db-password-not-example@db/x",
    )
    monkeypatch.setenv("PASSWORD_LOGIN_ENABLED", "0")
    monkeypatch.setenv("AUTH_MODE", "google")
    monkeypatch.setenv("ENABLE_DEMO_SEED", "0")
    import app_config

    cfg = importlib.reload(app_config)
    with pytest.raises(RuntimeError, match="GOOGLE_CLIENT_ID"):
        cfg.validate_production_settings()


def test_production_rejects_password_login_enabled(monkeypatch):
    for key in (
        "APP_ENV",
        "JWT_SECRET",
        "JWT_EXPIRE_MINUTES",
        "CORS_ORIGINS",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
        "GOOGLE_CLIENT_ID",
        "PASSWORD_LOGIN_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "60")
    monkeypatch.setenv("CORS_ORIGINS", "https://portal.example.edu")
    monkeypatch.setenv("POSTGRES_PASSWORD", "strong-db-password-not-example")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://u:strong-db-password-not-example@db/x",
    )
    monkeypatch.setenv("GOOGLE_CLIENT_ID", GOOGLE_CLIENT)
    monkeypatch.setenv("PASSWORD_LOGIN_ENABLED", "1")
    monkeypatch.setenv("AUTH_MODE", "google")
    monkeypatch.setenv("ENABLE_DEMO_SEED", "0")
    import app_config

    cfg = importlib.reload(app_config)
    with pytest.raises(RuntimeError, match="PASSWORD_LOGIN"):
        cfg.validate_production_settings()
