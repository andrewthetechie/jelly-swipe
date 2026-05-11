"""Add tmdb_cache table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_tmdb_cache"
down_revision = "0004_session_event_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tmdb_cache",
        sa.Column("media_id", sa.Text(), nullable=False),
        sa.Column("lookup_type", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("media_id", "lookup_type"),
    )


def downgrade() -> None:
    op.drop_table("tmdb_cache")
