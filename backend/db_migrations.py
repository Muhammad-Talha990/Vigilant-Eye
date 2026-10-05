"""Safe helpers for Alembic revision visibility (no secrets)."""

from __future__ import annotations

from pathlib import Path


def alembic_config_path() -> Path:
    return Path(__file__).resolve().parent / "alembic.ini"


def get_alembic_migration_status(connection=None) -> dict:
    """
    Return current / head revision and whether upgrades are pending.
    Never raises — returns error fields suitable for admin/health UIs.
    """
    out: dict = {
        "alembic_available": False,
        "current_revision": None,
        "head_revision": None,
        "migrations_pending": None,
        "error": None,
    }
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory
        from sqlalchemy import create_engine

        from database import DATABASE_URL, engine

        cfg = Config(str(alembic_config_path()))
        script = ScriptDirectory.from_config(cfg)
        heads = script.get_heads()
        head = heads[0] if heads else None
        out["head_revision"] = head
        out["alembic_available"] = True

        if connection is not None:
            ctx = MigrationContext.configure(connection)
            current = ctx.get_current_revision()
        else:
            with engine.connect() as conn:
                ctx = MigrationContext.configure(conn)
                current = ctx.get_current_revision()
        out["current_revision"] = current
        if head is None:
            out["migrations_pending"] = False
        elif current is None:
            out["migrations_pending"] = True
        else:
            out["migrations_pending"] = current != head
    except Exception as exc:  # noqa: BLE001
        out["error"] = type(exc).__name__
    return out


def run_alembic_upgrade_head() -> None:
    """Apply all pending migrations. Raises on failure."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(alembic_config_path()))
    # Ensure script location resolves relative to backend/
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parent / "alembic"))
    command.upgrade(cfg, "head")
