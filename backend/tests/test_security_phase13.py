"""
Phase 13 — production security configuration tests.

Avoids reloading main.py (keeps the shared TestClient app stable for other suites).
"""

from __future__ import annotations

import importlib

import jwt
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models.base import Base
from models.user import User
from schemas.user import UserCreate
from security import hash_password


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        db.add(
            User(
                name="Invig",
                email="invigilator@demo.com",
                password_hash=hash_password("Demo@123"),
                role="INVIGILATOR",
                is_active=True,
            )
        )
        db.add(
            User(
                name="HOD",
                email="hod@demo.com",
                password_hash=hash_password("Demo@123"),
                role="HOD",
                is_active=True,
            )
        )
        db.add(
            User(
                name="Inactive",
                email="inactive@demo.com",
                password_hash=hash_password("Demo@123"),
                role="INVIGILATOR",
                is_active=False,
            )
        )
        db.commit()
    finally:
        db.close()

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_user_create_password_min_eight():
    with pytest.raises(ValidationError):
        UserCreate(
            name="Short",
            email="short@demo.com",
            password="1234567",
            role="STUDENT",
        )
    ok = UserCreate(
        name="Ok",
        email="ok@demo.com",
        password="Demo@123",
        role="STUDENT",
    )
    assert ok.password == "Demo@123"


def test_app_config_docs_and_cors(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ENABLE_API_DOCS", raising=False)
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example,https://b.example")
    import app_config

    importlib.reload(app_config)
    assert app_config.IS_PRODUCTION is True
    assert app_config.ENABLE_API_DOCS is False
    assert app_config.cors_allow_origins() == [
        "https://a.example",
        "https://b.example",
    ]

    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    importlib.reload(app_config)
    assert app_config.IS_PRODUCTION is False
    assert app_config.ENABLE_API_DOCS is True
    assert "http://localhost:5173" in app_config.cors_allow_origins()


def test_invalid_and_missing_token(client):
    assert client.get("/ufm-cases").status_code == 401
    assert (
        client.get(
            "/ufm-cases", headers={"Authorization": "Bearer not-a-jwt"}
        ).status_code
        == 401
    )


def test_expired_token_rejected(client):
    from security import JWT_SECRET

    expired = jwt.encode(
        {
            "sub": "1",
            "email": "invigilator@demo.com",
            "role": "INVIGILATOR",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=5),
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_inactive_user_login_rejected(client):
    r = client.post(
        "/auth/login",
        json={"email": "inactive@demo.com", "password": "Demo@123"},
    )
    assert r.status_code == 403


def test_security_headers_present(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"
    assert "strict-origin-when-cross-origin" in (
        r.headers.get("referrer-policy") or ""
    )


def test_create_user_rejects_short_password_via_api(client):
    login = client.post(
        "/auth/login",
        json={"email": "hod@demo.com", "password": "Demo@123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    short = client.post(
        "/users",
        headers=headers,
        json={
            "name": "Short",
            "email": "shortpw@demo.com",
            "password": "1234567",
            "role": "STUDENT",
        },
    )
    assert short.status_code == 422
