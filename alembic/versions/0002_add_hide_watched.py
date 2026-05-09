"""Add hide_watched column to rooms table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_add_hide_watched"
down_revision = "0001_phase36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rooms",
        sa.Column("hide_watched", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("rooms", "hide_watched")
