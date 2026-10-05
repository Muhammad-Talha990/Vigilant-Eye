"""Baseline schema matching current VigilantEye models (Phase 22).

Fresh databases: upgrade creates all tables via SQLAlchemy metadata.
Existing databases that already match this schema: stamp this revision
without running upgrade (see docs/DATABASE.md).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260928_0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Import registry so metadata includes every model table.
    from model_registry import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    # Baseline downgrade is intentionally a no-op: dropping institutional
    # tables would destroy UFM history. Tear down only via disposable DBs.
    pass
