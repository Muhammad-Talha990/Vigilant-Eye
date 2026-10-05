"""Phase 23 — exam enrollments, invigilator assignments, operational indexes.

Additive only. Safe on empty enrollment/invigilator tables.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260928_0003_exam_ops"
down_revision: Union[str, Sequence[str], None] = "20260928_0002_integrity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "exam_enrollments" not in tables:
        op.create_table(
            "exam_enrollments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
            sa.Column(
                "student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False
            ),
            sa.UniqueConstraint(
                "exam_id", "student_id", name="uq_exam_enrollments_exam_student"
            ),
        )
        op.create_index("ix_exam_enrollments_exam_id", "exam_enrollments", ["exam_id"])
        op.create_index(
            "ix_exam_enrollments_student_id", "exam_enrollments", ["student_id"]
        )

    if "exam_invigilators" not in tables:
        op.create_table(
            "exam_invigilators",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.UniqueConstraint(
                "exam_id", "user_id", name="uq_exam_invigilators_exam_user"
            ),
        )
        op.create_index("ix_exam_invigilators_exam_id", "exam_invigilators", ["exam_id"])
        op.create_index("ix_exam_invigilators_user_id", "exam_invigilators", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "exam_invigilators" in tables:
        op.drop_table("exam_invigilators")
    if "exam_enrollments" in tables:
        op.drop_table("exam_enrollments")
