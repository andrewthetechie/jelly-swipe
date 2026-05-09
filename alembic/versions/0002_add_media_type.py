"""Add media_type column to matches table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_add_media_type"
down_revision = "0001_phase36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("media_type", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("matches", "media_type")
