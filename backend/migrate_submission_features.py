"""
OBSOLETE AFTER ALEMBIC (Phase 22) — classification A.

Historically additive ALTER scripts for submission features. Now covered by
models + Alembic baseline. Kept for reference; only invoked when
LEGACY_ADDITIVE_MIGRATIONS=1 (non-production).

Usage (legacy):
    python migrate_submission_features.py
"""

from sqlalchemy import inspect, text

from database import engine


def _add_column(table: str, column_sql: str, col_name: str) -> None:
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns(table)}
    if col_name in columns:
        print(f"SKIP  {table}.{col_name}")
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_sql}"))
    print(f"OK    {table}.{col_name}")


def migrate() -> None:
    _add_column(
        "ufm_cases",
        "signer_name VARCHAR(150)",
        "signer_name",
    )
    _add_column(
        "ufm_cases",
        "signed_at TIMESTAMP",
        "signed_at",
    )
    _add_column(
        "ufm_cases",
        "signature_ack BOOLEAN DEFAULT FALSE",
        "signature_ack",
    )
    _add_column(
        "case_reviews",
        "signer_name VARCHAR(150)",
        "signer_name",
    )
    _add_column(
        "case_reviews",
        "signed_at TIMESTAMP",
        "signed_at",
    )
    _add_column(
        "case_reviews",
        "signature_ack BOOLEAN DEFAULT FALSE",
        "signature_ack",
    )
    # Allow orphan evidence before a case exists (auto snapshot/clip)
    inspector = inspect(engine)
    evidence_cols = {col["name"]: col for col in inspector.get_columns("evidence")}
    if "case_id" in evidence_cols:
        # Best-effort: drop NOT NULL if present (Postgres)
        try:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE evidence ALTER COLUMN case_id DROP NOT NULL")
                )
            print("OK    evidence.case_id nullable")
        except Exception as exc:  # noqa: BLE001
            print(f"SKIP  evidence.case_id nullable ({exc})")
    added_seen = False
    inspector = inspect(engine)
    det_cols = {col["name"] for col in inspector.get_columns("detections")}
    if "is_seen" not in det_cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE detections ADD COLUMN is_seen BOOLEAN DEFAULT FALSE")
            )
        print("OK    detections.is_seen")
        added_seen = True
    else:
        print("SKIP  detections.is_seen")
    if added_seen:
        try:
            with engine.begin() as conn:
                conn.execute(text("UPDATE detections SET is_seen = TRUE"))
            print("OK    detections.is_seen backfill (existing → seen)")
        except Exception as exc:  # noqa: BLE001
            print(f"SKIP  detections.is_seen backfill ({exc})")
    _add_column(
        "detections",
        "is_demo BOOLEAN DEFAULT FALSE",
        "is_demo",
    )
    _add_column(
        "evidence",
        "is_demo BOOLEAN DEFAULT FALSE",
        "is_demo",
    )
    print("Done.")


if __name__ == "__main__":
    migrate()
