"""
Development / Docker startup bootstrap.

Waits for PostgreSQL, applies Alembic migrations, optionally seeds demo data.

Does not drop databases or tables. Safe to re-run.
Does not print secrets or demo passwords.

Production:
  - schema via Alembic only (no create_all)
  - demo seed forbidden by validate_production_settings

Development:
  - Alembic upgrade head
  - optional legacy additive scripts only if LEGACY_ADDITIVE_MIGRATIONS=1
  - demo seed when demo_seed_enabled()
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _wait_for_database(*, attempts: int = 60, delay_s: float = 2.0) -> None:
    from sqlalchemy import text

    from database import engine

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"PostgreSQL: READY (attempt {attempt}/{attempts})")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(
                f"PostgreSQL: NOT READY (attempt {attempt}/{attempts}) — waiting…"
            )
            time.sleep(delay_s)

    reason = type(last_error).__name__ if last_error else "unknown"
    print("PostgreSQL: NOT READY")
    print(f"Reason: could not connect after {attempts} attempts ({reason})")
    raise SystemExit(1)


def _ensure_schema() -> None:
    from app_config import IS_PRODUCTION
    from db_migrations import run_alembic_upgrade_head

    print("Schema: applying Alembic migrations (upgrade head)…")
    run_alembic_upgrade_head()
    print("Schema: Alembic READY")

    # Optional bridge for older environments that still need the hand-written
    # additive ALTER scripts. Idempotent; off by default once Alembic is adopted.
    legacy = (os.getenv("LEGACY_ADDITIVE_MIGRATIONS") or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if legacy and not IS_PRODUCTION:
        from migrate_student_user_link import migrate as migrate_student_link
        from migrate_submission_features import migrate as migrate_submission

        print("Schema: LEGACY_ADDITIVE_MIGRATIONS=1 — running obsolete ALTER scripts…")
        migrate_student_link()
        migrate_submission()
    elif legacy and IS_PRODUCTION:
        print(
            "Schema: LEGACY_ADDITIVE_MIGRATIONS ignored in production "
            "(Alembic only)"
        )


def _seed_demo() -> None:
    from app_config import demo_seed_enabled

    if not demo_seed_enabled():
        print(
            "Demo seed: SKIPPED "
            "(production or ENABLE_DEMO_SEED=0; "
            "set ENABLE_DEMO_SEED=1 only for explicit lab/demo)"
        )
        return

    from seed_demo_cameras import seed as seed_cameras
    from seed_demo_users import seed as seed_users

    print("Demo seed: users / DEMO001…")
    seed_users(quiet=True)
    print("Demo seed: rooms / cameras / exam…")
    seed_cameras(quiet=True)
    print("Demo seed: READY (idempotent; see README for demo accounts)")


def main() -> None:
    print("=== VigilantEye bootstrap ===")
    from app_config import validate_production_settings

    validate_production_settings()
    _wait_for_database()
    _ensure_schema()
    _seed_demo()
    print("Bootstrap: COMPLETE")


if __name__ == "__main__":
    main()
