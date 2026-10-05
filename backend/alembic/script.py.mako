"""Alembic script template."""

<%= imports %>

# revision identifiers, used by Alembic.
revision = <%= revision %>
down_revision = <%= down_revision %>
branch_labels = <%= branch_labels %>
depends_on = <%= depends_on %>


def upgrade() -> None:
    <%= upgrades %>


def downgrade() -> None:
    <%= downgrades %>
