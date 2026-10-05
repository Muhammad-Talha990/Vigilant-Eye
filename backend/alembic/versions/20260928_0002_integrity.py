"""Integrity hardening: evidence→detection FK, result_controls unique, indexes.

Verified against live data integrity audit (Phase 22): zero conflicting rows.
Delete strategy for evidence.detection_id: SET NULL (preserve evidence rows).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260928_0002_integrity"
down_revision: Union[str, Sequence[str], None] = "20260928_0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- evidence.detection_id FK (SET NULL on detection delete) ---
    evidence_fks = {fk["name"] for fk in inspector.get_foreign_keys("evidence")}
    if "fk_evidence_detection_id_detections" not in evidence_fks:
        # Clear any orphan pointers before adding the FK (audit found zero;
        # still defensive for other environments).
        op.execute(
            sa.text(
                """
                UPDATE evidence
                SET detection_id = NULL
                WHERE detection_id IS NOT NULL
                  AND detection_id NOT IN (SELECT id FROM detections)
                """
            )
        )
        op.create_foreign_key(
            "fk_evidence_detection_id_detections",
            "evidence",
            "detections",
            ["detection_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # --- one result control per case ---
    rc_uniques = {
        tuple(u.get("column_names") or [])
        for u in inspector.get_unique_constraints("result_controls")
    }
    rc_indexes = {
        tuple(i.get("column_names") or []): i
        for i in inspector.get_indexes("result_controls")
    }
    if ("case_id",) not in rc_uniques and not any(
        i.get("unique") and tuple(i.get("column_names") or []) == ("case_id",)
        for i in inspector.get_indexes("result_controls")
    ):
        op.create_unique_constraint(
            "uq_result_controls_case_id",
            "result_controls",
            ["case_id"],
        )

    # --- query-oriented indexes (skip if already present) ---
    def ensure_index(table: str, name: str, columns: list[str]) -> None:
        existing = {i["name"] for i in sa.inspect(bind).get_indexes(table)}
        if name in existing:
            return
        op.create_index(name, table, columns)

    ensure_index("notifications", "ix_notifications_user_id_is_read", ["user_id", "is_read"])
    ensure_index("audit_logs", "ix_audit_logs_action", ["action"])
    ensure_index("audit_logs", "ix_audit_logs_timestamp", ["timestamp"])
    ensure_index("users", "ix_users_role", ["role"])
    ensure_index("users", "ix_users_is_active", ["is_active"])
    ensure_index("ufm_cases", "ix_ufm_cases_status_updated", ["status", "updated_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table, name in [
        ("ufm_cases", "ix_ufm_cases_status_updated"),
        ("users", "ix_users_is_active"),
        ("users", "ix_users_role"),
        ("audit_logs", "ix_audit_logs_timestamp"),
        ("audit_logs", "ix_audit_logs_action"),
        ("notifications", "ix_notifications_user_id_is_read"),
    ]:
        names = {i["name"] for i in inspector.get_indexes(table)}
        if name in names:
            op.drop_index(name, table_name=table)

    uq_names = {
        u["name"] for u in sa.inspect(bind).get_unique_constraints("result_controls")
    }
    if "uq_result_controls_case_id" in uq_names:
        op.drop_constraint(
            "uq_result_controls_case_id", "result_controls", type_="unique"
        )

    fk_names = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys("evidence")}
    if "fk_evidence_detection_id_detections" in fk_names:
        op.drop_constraint(
            "fk_evidence_detection_id_detections", "evidence", type_="foreignkey"
        )
