"""
Database engine for VigilantEye.

Canonical setting: DATABASE_URL
  postgresql+psycopg://USER:PASSWORD@HOST:PORT/DBNAME

Fallback (legacy local .env): DATABASE_HOST, DATABASE_PORT, DATABASE_NAME,
DATABASE_USER, DATABASE_PASSWORD — used only when DATABASE_URL is unset.

Pool settings are environment-driven for university deployment tuning.
"""

from __future__ import annotations

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()


def _build_database_url() -> str:
    explicit = (os.getenv("DATABASE_URL") or "").strip()
    if explicit:
        return explicit

    host = (os.getenv("DATABASE_HOST") or "").strip()
    port = (os.getenv("DATABASE_PORT") or "").strip()
    name = (os.getenv("DATABASE_NAME") or "").strip()
    user = (os.getenv("DATABASE_USER") or "").strip()
    password = os.getenv("DATABASE_PASSWORD")
    if password is None:
        password = ""

    missing = [
        key
        for key, val in [
            ("DATABASE_HOST", host),
            ("DATABASE_PORT", port),
            ("DATABASE_NAME", name),
            ("DATABASE_USER", user),
        ]
        if not val
    ]
    if missing:
        raise RuntimeError(
            "Database is not configured. Set DATABASE_URL (recommended), "
            "or set DATABASE_HOST, DATABASE_PORT, DATABASE_NAME, "
            "DATABASE_USER, and DATABASE_PASSWORD. "
            "See .env.example and backend/.env.example."
        )

    user_q = quote_plus(user)
    pass_q = quote_plus(password)
    return f"postgresql+psycopg://{user_q}:{pass_q}@{host}:{port}/{name}"


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


DATABASE_URL = _build_database_url()

# Conservative defaults for a mid-size university portal.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=_int_env("DB_POOL_SIZE", 5),
    max_overflow=_int_env("DB_MAX_OVERFLOW", 10),
    pool_timeout=_int_env("DB_POOL_TIMEOUT", 30),
    pool_recycle=_int_env("DB_POOL_RECYCLE", 1800),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Yield one session per request; rollback on error, always close."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
