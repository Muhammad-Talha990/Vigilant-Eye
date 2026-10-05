"""Add detections.model_version for AI event auditability.

Revision ID: 20261004_0006_detection_model_version
Revises: 20260930_0005_case_camera
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261004_0006_detection_model_version"
down_revision: Union[str, Sequence[str], None] = "20260930_0005_case_camera"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("detections")}
    if "model_version" not in columns:
        op.add_column(
            "detections",
            sa.Column("model_version", sa.String(length=120), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("detections")}
    if "model_version" in columns:
        op.drop_column("detections", "model_version")
