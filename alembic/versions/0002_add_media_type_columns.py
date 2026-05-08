"""Add include_movies and include_tv_shows columns to rooms table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_media_type"
down_revision = "0001_phase36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "rooms",
        sa.Column("include_movies", sa.Integer(), nullable=False, server_default=sa.text("1")),
    )
    op.add_column(
        "rooms",
        sa.Column("include_tv_shows", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("rooms", "include_tv_shows")
    op.drop_column("rooms", "include_movies")
