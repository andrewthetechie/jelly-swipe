"""Phase 36 baseline schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_phase36"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rooms",
        sa.Column("pairing_code", sa.Text(), primary_key=True),
        sa.Column("movie_data", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("ready", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("current_genre", sa.Text(), nullable=False, server_default=sa.text("'All'")),
        sa.Column("solo_mode", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_match_data", sa.Text(), nullable=True),
        sa.Column("deck_position", sa.Text(), nullable=True),
        sa.Column("deck_order", sa.Text(), nullable=True),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("session_id", sa.Text(), primary_key=True),
        sa.Column("jellyfin_token", sa.Text(), nullable=False),
        sa.Column("jellyfin_user_id", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
    )
    op.create_index("ix_auth_sessions_created_at", "auth_sessions", ["created_at"])

    op.create_table(
        "swipes",
        sa.Column("room_code", sa.Text(), nullable=False),
        sa.Column("movie_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["room_code"], ["rooms.pairing_code"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["auth_sessions.session_id"], ondelete="SET NULL"),
    )
    op.create_index("ix_swipes_room_movie_direction", "swipes", ["room_code", "movie_id", "direction"])
    op.create_index("ix_swipes_room_movie_session", "swipes", ["room_code", "movie_id", "session_id"])

    op.create_table(
        "matches",
        sa.Column("room_code", sa.Text(), nullable=False),
        sa.Column("movie_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("thumb", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("deep_link", sa.Text(), nullable=True),
        sa.Column("rating", sa.Text(), nullable=True),
        sa.Column("duration", sa.Text(), nullable=True),
        sa.Column("year", sa.Text(), nullable=True),
        sa.UniqueConstraint("room_code", "movie_id", "user_id", name="uq_matches_room_movie_user"),
    )
    op.create_index("ix_matches_status_user_id", "matches", ["status", "user_id"])


def downgrade() -> None:
    op.drop_index("ix_matches_status_user_id", table_name="matches")
    op.drop_table("matches")
    op.drop_index("ix_swipes_room_movie_session", table_name="swipes")
    op.drop_index("ix_swipes_room_movie_direction", table_name="swipes")
    op.drop_table("swipes")
    op.drop_index("ix_auth_sessions_created_at", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("rooms")
