"""
Phase 17 — AUTH_MODE separation and explicit Google user provisioning.
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
from models.student import Student
from models.user import User
from provision_test_google_users import provision
from security import hash_password

GOOGLE_CLIENT = "1234567890-phase17.apps.googleusercontent.com"


def _reload(monkeypatch, **env):
    for key in (
        "APP_ENV",
        "AUTH_MODE",
        "GOOGLE_CLIENT_ID",
        "PASSWORD_LOGIN_ENABLED",
        "ENABLE_DEMO_SEED",
        "CORS_ORIGINS",
        "JWT_SECRET",
        "JWT_EXPIRE_MINUTES",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import app_config

    return importlib.reload(app_config)


@pytest.fixture(autouse=True)
def _restore_demo_mode(monkeypatch):
    yield
    cfg = _reload(
        monkeypatch,
        APP_ENV="development",
        AUTH_MODE="demo",
        PASSWORD_LOGIN_ENABLED="1",
    )
    import google_auth
    import main as main_mod

    importlib.reload(google_auth)
    main_mod.password_login_enabled = cfg.password_login_enabled
    main_mod.google_auth_enabled = cfg.google_auth_enabled
    main_mod.auth_mode = cfg.auth_mode
    main_mod.demo_helpers_enabled = cfg.demo_helpers_enabled
    main_mod.verify_google_id_token = google_auth.verify_google_id_token


def test_auth_mode_demo_hides_google_even_with_client_id(monkeypatch):
    cfg = _reload(
        monkeypatch,
        APP_ENV="development",
        AUTH_MODE="demo",
        GOOGLE_CLIENT_ID=GOOGLE_CLIENT,
    )
    assert cfg.auth_mode() == "demo"
    assert cfg.password_login_enabled() is True
    assert cfg.google_auth_enabled() is False
    assert cfg.demo_helpers_enabled() is True
    assert cfg.demo_seed_enabled() is True


def test_auth_mode_google_enables_google_disables_password(monkeypatch):
    cfg = _reload(
        monkeypatch,
        APP_ENV="development",
        AUTH_MODE="google",
        GOOGLE_CLIENT_ID=GOOGLE_CLIENT,
    )
    assert cfg.auth_mode() == "google"
    assert cfg.google_auth_enabled() is True
    assert cfg.password_login_enabled() is False
    assert cfg.demo_helpers_enabled() is False
    assert cfg.demo_seed_enabled() is False


def test_auth_mode_both_allows_google_and_password(monkeypatch):
    cfg = _reload(
        monkeypatch,
        APP_ENV="development",
        AUTH_MODE="both",
        GOOGLE_CLIENT_ID=GOOGLE_CLIENT,
    )
    assert cfg.auth_mode() == "both"
    assert cfg.google_auth_enabled() is True
    assert cfg.password_login_enabled() is True
    assert cfg.demo_helpers_enabled() is True


def test_auth_mode_google_without_client_id(monkeypatch):
    cfg = _reload(monkeypatch, APP_ENV="development", AUTH_MODE="google")
    assert cfg.google_auth_enabled() is False
    assert cfg.password_login_enabled() is False


def test_production_rejects_auth_mode_demo(monkeypatch):
    cfg = _reload(
        monkeypatch,
        APP_ENV="production",
        AUTH_MODE="demo",
        JWT_SECRET="x" * 32,
        JWT_EXPIRE_MINUTES="60",
        CORS_ORIGINS="https://portal.example.edu",
        POSTGRES_PASSWORD="strong-db-password-not-example",
        DATABASE_URL="postgresql+psycopg://u:strong-db-password-not-example@db/x",
        GOOGLE_CLIENT_ID=GOOGLE_CLIENT,
        PASSWORD_LOGIN_ENABLED="0",
        ENABLE_DEMO_SEED="0",
    )
    with pytest.raises(RuntimeError, match="AUTH_MODE"):
        cfg.validate_production_settings()


def test_production_rejects_auth_mode_both(monkeypatch):
    cfg = _reload(
        monkeypatch,
        APP_ENV="production",
        AUTH_MODE="both",
        JWT_SECRET="x" * 32,
        JWT_EXPIRE_MINUTES="60",
        CORS_ORIGINS="https://portal.example.edu",
        POSTGRES_PASSWORD="strong-db-password-not-example",
        DATABASE_URL="postgresql+psycopg://u:strong-db-password-not-example@db/x",
        GOOGLE_CLIENT_ID=GOOGLE_CLIENT,
        PASSWORD_LOGIN_ENABLED="0",
        ENABLE_DEMO_SEED="0",
    )
    with pytest.raises(RuntimeError, match="AUTH_MODE"):
        cfg.validate_production_settings()


def test_production_accepts_auth_mode_google(monkeypatch):
    cfg = _reload(
        monkeypatch,
        APP_ENV="production",
        AUTH_MODE="google",
        JWT_SECRET="x" * 32,
        JWT_EXPIRE_MINUTES="60",
        CORS_ORIGINS="https://portal.example.edu",
        POSTGRES_PASSWORD="strong-db-password-not-example",
        DATABASE_URL="postgresql+psycopg://u:strong-db-password-not-example@db/x",
        GOOGLE_CLIENT_ID=GOOGLE_CLIENT,
        PASSWORD_LOGIN_ENABLED="0",
        ENABLE_DEMO_SEED="0",
    )
    cfg.validate_production_settings()
    assert cfg.auth_mode() == "google"


def test_student_domain_does_not_auto_authorize():
    """Provision is explicit — domain alone is never enough (no auto path)."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with patch("provision_test_google_users.SessionLocal", TestingSessionLocal):
        # Creating an unrelated Student without User must not imply login rights.
        db = TestingSessionLocal()
        db.add(
            Student(
                student_id="999999",
                name="Orphan",
                department="CS",
                program="BSCS",
                user_id=None,
            )
        )
        db.commit()
        db.close()

        # Explicit provision creates User + link
        user = provision(
            email="232514@students.au.edu.pk",
            role="STUDENT",
            student_roll="232514",
        )
        assert user.email == "232514@students.au.edu.pk"
        assert user.role == "STUDENT"

        db = TestingSessionLocal()
        orphan = db.scalar(select(Student).where(Student.student_id == "999999"))
        linked = db.scalar(select(Student).where(Student.student_id == "232514"))
        assert orphan.user_id is None
        assert linked.user_id == user.id
        # Domain peer without User row
        assert (
            db.scalar(
                select(User).where(User.email == "999999@students.au.edu.pk")
            )
            is None
        )
        db.close()


def test_provision_staff_role_explicit():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    with patch("provision_test_google_users.SessionLocal", TestingSessionLocal):
        user = provision(email="realstaff@gmail.com", role="HOD", name="Real HOD")
        assert user.role == "HOD"
        assert user.email == "realstaff@gmail.com"


def test_provision_rejects_invalid_role():
    with pytest.raises(ValueError, match="Invalid role"):
        provision(email="x@y.com", role="SUPERADMIN")


def test_google_mode_password_login_blocked(monkeypatch):
    cfg = _reload(
        monkeypatch,
        APP_ENV="development",
        AUTH_MODE="google",
        GOOGLE_CLIENT_ID=GOOGLE_CLIENT,
    )
    import main as main_mod

    main_mod.password_login_enabled = cfg.password_login_enabled
    main_mod.google_auth_enabled = cfg.google_auth_enabled

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(
        User(
            name="HOD",
            email="hod@demo.com",
            password_hash=hash_password("Demo@123"),
            role="HOD",
            is_active=True,
        )
    )
    db.commit()

    def override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            r = client.post(
                "/auth/login",
                json={"email": "hod@demo.com", "password": "Demo@123"},
            )
            assert r.status_code == 403
            cfg_r = client.get("/auth/config")
            assert cfg_r.status_code == 200
            body = cfg_r.json()
            assert body["auth_mode"] == "google"
            assert body["password_login_enabled"] is False
            assert body["google_auth_enabled"] is True
            assert body["demo_helpers_enabled"] is False
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_demo_mode_password_still_works(monkeypatch):
    cfg = _reload(
        monkeypatch,
        APP_ENV="development",
        AUTH_MODE="demo",
        PASSWORD_LOGIN_ENABLED="1",
    )
    import main as main_mod

    main_mod.password_login_enabled = cfg.password_login_enabled
    main_mod.google_auth_enabled = cfg.google_auth_enabled
    main_mod.auth_mode = cfg.auth_mode
    main_mod.demo_helpers_enabled = cfg.demo_helpers_enabled

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(
        User(
            name="Inv",
            email="invigilator@demo.com",
            password_hash=hash_password("Demo@123"),
            role="INVIGILATOR",
            is_active=True,
        )
    )
    db.commit()

    def override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            r = client.post(
                "/auth/login",
                json={"email": "invigilator@demo.com", "password": "Demo@123"},
            )
            assert r.status_code == 200
            cfg_r = client.get("/auth/config").json()
            assert cfg_r["auth_mode"] == "demo"
            assert cfg_r["google_auth_enabled"] is False
            assert cfg_r["demo_helpers_enabled"] is True
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_authorized_google_student_under_google_mode(monkeypatch):
    cfg = _reload(
        monkeypatch,
        APP_ENV="development",
        AUTH_MODE="google",
        GOOGLE_CLIENT_ID=GOOGLE_CLIENT,
    )
    import google_auth
    import main as main_mod

    importlib.reload(google_auth)
    main_mod.password_login_enabled = cfg.password_login_enabled
    main_mod.google_auth_enabled = cfg.google_auth_enabled
    main_mod.verify_google_id_token = google_auth.verify_google_id_token

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(
        User(
            name="Student",
            email="232514@students.au.edu.pk",
            password_hash=hash_password("unused-password-xx"),
            role="STUDENT",
            is_active=True,
        )
    )
    db.commit()

    def override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override
    identity = GoogleIdentity(
        email=normalize_email("232514@students.au.edu.pk"),
        email_verified=True,
        subject="sub",
        name="Student",
    )
    try:
        with TestClient(app) as client:
            with patch("main.verify_google_id_token", return_value=identity):
                r = client.post(
                    "/auth/google", json={"id_token": "fake." + ("y" * 40)}
                )
            assert r.status_code == 200
            assert r.json()["user"]["role"] == "STUDENT"
            token = r.json()["access_token"]
            denied = client.get(
                "/detections", headers={"Authorization": f"Bearer {token}"}
            )
            assert denied.status_code == 403
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_unknown_google_does_not_create_user(monkeypatch):
    cfg = _reload(
        monkeypatch,
        APP_ENV="development",
        AUTH_MODE="google",
        GOOGLE_CLIENT_ID=GOOGLE_CLIENT,
    )
    import main as main_mod

    main_mod.google_auth_enabled = cfg.google_auth_enabled

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    def override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override
    identity = GoogleIdentity(
        email="unauthorized.person@gmail.com",
        email_verified=True,
        subject="sub",
        name="Nope",
    )
    try:
        with TestClient(app) as client:
            with patch("main.verify_google_id_token", return_value=identity):
                r = client.post(
                    "/auth/google", json={"id_token": "fake." + ("z" * 40)}
                )
            assert r.status_code == 403
            assert (
                db.scalar(
                    select(User).where(
                        User.email == "unauthorized.person@gmail.com"
                    )
                )
                is None
            )
    finally:
        app.dependency_overrides.clear()
        db.close()
