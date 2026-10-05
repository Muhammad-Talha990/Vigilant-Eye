"""Add recovered-materials fields for official AU UFM incident form.

Additive only. Existing cases keep NULL recovered_materials.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260930_0004_ufm_form"
down_revision: Union[str, Sequence[str], None] = "20260928_0003_exam_ops"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("ufm_cases")}

    if "recovered_materials" not in columns:
        op.add_column(
            "ufm_cases",
            sa.Column("recovered_materials", sa.Text(), nullable=True),
        )
    if "recovered_other_detail" not in columns:
        op.add_column(
            "ufm_cases",
            sa.Column("recovered_other_detail", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("ufm_cases")}
    if "recovered_other_detail" in columns:
        op.drop_column("ufm_cases", "recovered_other_detail")
    if "recovered_materials" in columns:
        op.drop_column("ufm_cases", "recovered_materials")
