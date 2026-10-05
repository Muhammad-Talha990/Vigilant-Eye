"""
OBSOLETE AFTER ALEMBIC (Phase 22) — classification A.

Historically added students.user_id for portal linking. Now covered by models +
Alembic baseline. Kept for reference; only invoked when
LEGACY_ADDITIVE_MIGRATIONS=1 (non-production).

Usage (legacy):
    python migrate_student_user_link.py
"""

from sqlalchemy import inspect, text

from database import engine


def migrate() -> None:
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns("students")}

    if "user_id" in columns:
        print("SKIP  students.user_id already exists")
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE students
                ADD COLUMN user_id INTEGER UNIQUE
                REFERENCES users(id)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_students_user_id
                ON students (user_id)
                """
            )
        )

    print("OK    added students.user_id (unique FK -> users.id)")


if __name__ == "__main__":
    migrate()
