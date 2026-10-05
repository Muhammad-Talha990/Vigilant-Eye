"""
Phase 15 — production config validation and demo-seed gating.
"""

from __future__ import annotations

import importlib

import pytest


def _reload_app_config(monkeypatch, **env):
    for key in (
        "APP_ENV",
        "ENABLE_API_DOCS",
        "CORS_ORIGINS",
        "JWT_SECRET",
        "JWT_EXPIRE_MINUTES",
        "POSTGRES_PASSWORD",
        "DATABASE_URL",
        "ENABLE_DEMO_SEED",
        "GOOGLE_CLIENT_ID",
        "PASSWORD_LOGIN_ENABLED",
        "AUTH_MODE",
    ):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    import app_config

    return importlib.reload(app_config)


def test_production_rejects_missing_cors(monkeypatch):
    cfg = _reload_app_config(
        monkeypatch,
        APP_ENV="production",
        JWT_SECRET="x" * 32,
        JWT_EXPIRE_MINUTES="60",
        POSTGRES_PASSWORD="strong-db-password-not-example",
        DATABASE_URL="postgresql+psycopg://u:strong-db-password-not-example@db/x",
    )
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        cfg.validate_production_settings()


def test_production_rejects_placeholder_jwt(monkeypatch):
    cfg = _reload_app_config(
        monkeypatch,
        APP_ENV="production",
        JWT_SECRET="CHANGE_ME_LOCAL_ONLY_USE_LONG_RANDOM",
        JWT_EXPIRE_MINUTES="60",
        CORS_ORIGINS="https://portal.example.edu",
        POSTGRES_PASSWORD="strong-db-password-not-example",
        DATABASE_URL="postgresql+psycopg://u:strong-db-password-not-example@db/x",
    )
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        cfg.validate_production_settings()


def test_production_rejects_jwt_ttl_over_60(monkeypatch):
    cfg = _reload_app_config(
        monkeypatch,
        APP_ENV="production",
        JWT_SECRET="x" * 32,
        JWT_EXPIRE_MINUTES="480",
        CORS_ORIGINS="https://portal.example.edu",
        POSTGRES_PASSWORD="strong-db-password-not-example",
        DATABASE_URL="postgresql+psycopg://u:strong-db-password-not-example@db/x",
    )
    with pytest.raises(RuntimeError, match="JWT_EXPIRE_MINUTES"):
        cfg.validate_production_settings()


def test_production_rejects_cors_wildcard(monkeypatch):
    cfg = _reload_app_config(
        monkeypatch,
        APP_ENV="production",
        JWT_SECRET="x" * 32,
        JWT_EXPIRE_MINUTES="60",
        CORS_ORIGINS="*",
        POSTGRES_PASSWORD="strong-db-password-not-example",
        DATABASE_URL="postgresql+psycopg://u:strong-db-password-not-example@db/x",
    )
    with pytest.raises(RuntimeError, match="wildcard"):
        cfg.validate_production_settings()
    with pytest.raises(RuntimeError, match="wildcard"):
        cfg.cors_allow_origins()


def test_production_accepts_valid_settings(monkeypatch):
    cfg = _reload_app_config(
        monkeypatch,
        APP_ENV="production",
        JWT_SECRET="x" * 32,
        JWT_EXPIRE_MINUTES="60",
        CORS_ORIGINS="https://portal.example.edu",
        POSTGRES_PASSWORD="strong-db-password-not-example",
        DATABASE_URL="postgresql+psycopg://u:strong-db-password-not-example@db/x",
        ENABLE_DEMO_SEED="0",
        GOOGLE_CLIENT_ID="1234567890-abcdefg.apps.googleusercontent.com",
        PASSWORD_LOGIN_ENABLED="0",
        AUTH_MODE="google",
    )
    cfg.validate_production_settings()
    assert cfg.cors_allow_origins() == ["https://portal.example.edu"]
    assert cfg.demo_seed_enabled() is False
    assert cfg.google_auth_enabled() is True
    assert cfg.password_login_enabled() is False
    assert cfg.auth_mode() == "google"


def test_demo_seed_default_development(monkeypatch):
    cfg = _reload_app_config(monkeypatch, APP_ENV="development")
    assert cfg.demo_seed_enabled() is True


def test_demo_seed_off_in_production_unless_forced(monkeypatch):
    cfg = _reload_app_config(monkeypatch, APP_ENV="production")
    assert cfg.demo_seed_enabled() is False
    cfg = _reload_app_config(
        monkeypatch, APP_ENV="production", ENABLE_DEMO_SEED="1"
    )
    assert cfg.demo_seed_enabled() is True


def test_development_cors_defaults_unchanged(monkeypatch):
    cfg = _reload_app_config(monkeypatch, APP_ENV="development")
    origins = cfg.cors_allow_origins()
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins
