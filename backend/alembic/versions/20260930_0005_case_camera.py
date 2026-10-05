"""Add nullable ufm_cases.camera_id FK to cameras.id.

Existing cases remain NULL (Not recorded). No backfill of guessed cameras.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260930_0005_case_camera"
down_revision: Union[str, Sequence[str], None] = "20260930_0004_ufm_form"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("ufm_cases")}
    fks = {fk["name"] for fk in inspector.get_foreign_keys("ufm_cases")}

    if "camera_id" not in columns:
        op.add_column(
            "ufm_cases",
            sa.Column("camera_id", sa.Integer(), nullable=True),
        )
    if "fk_ufm_cases_camera_id_cameras" not in fks:
        op.create_foreign_key(
            "fk_ufm_cases_camera_id_cameras",
            "ufm_cases",
            "cameras",
            ["camera_id"],
            ["id"],
        )
    # Index for filtering by camera (optional but useful)
    indexes = {ix["name"] for ix in inspector.get_indexes("ufm_cases")}
    if "ix_ufm_cases_camera_id" not in indexes:
        op.create_index("ix_ufm_cases_camera_id", "ufm_cases", ["camera_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {ix["name"] for ix in inspector.get_indexes("ufm_cases")}
    fks = {fk["name"] for fk in inspector.get_foreign_keys("ufm_cases")}
    columns = {c["name"] for c in inspector.get_columns("ufm_cases")}

    if "ix_ufm_cases_camera_id" in indexes:
        op.drop_index("ix_ufm_cases_camera_id", table_name="ufm_cases")
    if "fk_ufm_cases_camera_id_cameras" in fks:
        op.drop_constraint(
            "fk_ufm_cases_camera_id_cameras", "ufm_cases", type_="foreignkey"
        )
    if "camera_id" in columns:
        op.drop_column("ufm_cases", "camera_id")
