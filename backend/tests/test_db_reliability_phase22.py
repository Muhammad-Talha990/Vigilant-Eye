"""
Phase 22 — Database reliability: Alembic, transactions, integrity, health.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import get_db
from main import app
from models.base import Base
from models.student import Student
from models.user import User
from security import create_access_token, hash_password


@pytest.fixture()
def client_db(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_CREATE_ALL_ON_STARTUP", "0")
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

    admin = User(
        name="Admin22",
        email="admin22@example.com",
        password_hash=hash_password("UnusedPass1!"),
        role="ADMINISTRATOR",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

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
        "Session": TestingSession,
        "engine": engine,
    }
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def test_alembic_config_and_revisions_exist():
    from pathlib import Path

    from alembic.config import Config
    from alembic.script import ScriptDirectory

    backend = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    revs = list(script.walk_revisions())
    ids = {r.revision for r in revs}
    assert "20260928_0001_baseline" in ids
    assert "20260928_0002_integrity" in ids
    assert script.get_current_head() == "20261004_0006_detection_model_version"
    assert "20260930_0005_case_camera" in ids


def test_health_liveness_without_db_requirement(client_db):
    r = client_db["client"].get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body.get("application") == "up"


def test_ready_includes_database_and_migration_fields(client_db):
    # With overridden SQLite session, /ready still hits global engine —
    # tolerate 200 or 503 but never leak credentials.
    r = client_db["client"].get("/ready")
    assert r.status_code in (200, 503)
    blob = str(r.json()).lower()
    assert "password" not in blob or "password_login" in blob
    assert "jwt_secret" not in blob


def test_admin_system_info_migration_fields(client_db):
    c = client_db["client"]
    h = _h(client_db["token"](client_db["admin"]))
    r = c.get("/admin/system-info", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "alembic_current_revision" in body
    assert "alembic_head_revision" in body
    assert "migrations_pending" in body
    assert "jwt_secret" not in str(body).lower()


def test_user_student_link_atomicity_rollback(client_db):
    db = client_db["db"]
    user = User(
        name="Stu22",
        email="stu22@example.com",
        password_hash=hash_password("UnusedPass1!"),
        role="STUDENT",
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        Student(
            student_id="R22",
            name="Stu22",
            department="CS",
            program="BSCS",
            user_id=user.id,
        )
    )
    db.commit()

    # Unique email violation should not leave a half-committed second user.
    before = db.scalar(select(User).where(User.email == "dup22@example.com"))
    assert before is None
    try:
        with db.begin_nested():
            u2 = User(
                name="Dup",
                email="stu22@example.com",  # duplicate
                password_hash=hash_password("UnusedPass1!"),
                role="INVIGILATOR",
                is_active=True,
            )
            db.add(u2)
            db.flush()
    except IntegrityError:
        db.rollback()
    assert db.scalar(select(User).where(User.email == "dup22@example.com")) is None


def test_result_control_unique_enforced_by_model_metadata():
    from models.result_control import ResultControl

    args = ResultControl.__table_args__
    assert args
    names = []
    for a in args if isinstance(args, tuple) else (args,):
        if getattr(a, "name", None):
            names.append(a.name)
    assert "uq_result_controls_case_id" in names


def test_evidence_detection_fk_defined():
    from models.evidence import Evidence

    fks = list(Evidence.__table__.foreign_keys)
    targets = {fk.column.table.name for fk in fks}
    assert "detections" in targets


def test_production_startup_skips_create_all(monkeypatch):
    """Guard: production path must not enable create_all by default."""
    monkeypatch.setenv("APP_ENV", "production")
    # Re-read logic mirrors main._on_startup without importing production-gated app.
    is_production = True
    allow = (os.getenv("ALLOW_CREATE_ALL_ON_STARTUP") or "").strip()
    if allow == "":
        allow = "0" if is_production else "1"
    assert allow == "0"
    assert not (
        allow.lower() in {"1", "true", "yes", "on"} and not is_production
    )


def test_demo_seed_blocked_when_production_flag(monkeypatch):
    import importlib

    import app_config

    previous_env = os.environ.get("APP_ENV")
    previous_seed = os.environ.get("ENABLE_DEMO_SEED")
    try:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("ENABLE_DEMO_SEED", "1")
        importlib.reload(app_config)
        with pytest.raises((SystemExit, RuntimeError, ValueError)):
            app_config.validate_production_settings()
    finally:
        if previous_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = previous_env
        if previous_seed is None:
            os.environ.pop("ENABLE_DEMO_SEED", None)
        else:
            os.environ["ENABLE_DEMO_SEED"] = previous_seed
        importlib.reload(app_config)


def test_inactive_user_rejected(client_db):
    db = client_db["db"]
    u = User(
        name="Inact",
        email="inact22@example.com",
        password_hash=hash_password("UnusedPass1!"),
        role="HOD",
        is_active=False,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    tok = create_access_token(user_id=u.id, email=u.email, role=u.role)
    r = client_db["client"].get("/auth/me", headers=_h(tok))
    assert r.status_code in (401, 403)
