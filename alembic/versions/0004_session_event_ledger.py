"""Add session_instances and session_events tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_session_event_ledger"
down_revision = "0003_add_hide_watched"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create session_instances table
    op.create_table(
        "session_instances",
        sa.Column("instance_id", sa.Text(), nullable=False),
        sa.Column("pairing_code", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("closed_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("instance_id"),
    )

    # Create session_events table
    op.create_table(
        "session_events",
        sa.Column("event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_instance_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
        sa.ForeignKeyConstraint(
            ["session_instance_id"], ["session_instances.instance_id"]
        ),
    )

    # Create index on (session_instance_id, event_id) for efficient replay reads
    op.create_index(
        "ix_session_events_session_instance_id_event_id",
        "session_events",
        ["session_instance_id", "event_id"],
    )

    # Drop rooms.last_match_data column
    op.drop_column("rooms", "last_match_data")


def downgrade() -> None:
    # Re-add rooms.last_match_data column
    op.add_column(
        "rooms",
        sa.Column("last_match_data", sa.Text(), nullable=True),
    )

    # Drop index
    op.drop_index(
        "ix_session_events_session_instance_id_event_id",
        table_name="session_events",
    )

    # Drop session_events table
    op.drop_table("session_events")

    # Drop session_instances table
    op.drop_table("session_instances")
