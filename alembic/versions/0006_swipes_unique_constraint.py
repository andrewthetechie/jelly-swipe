"""Add unique constraint on swipes composite key."""

from __future__ import annotations

from alembic import op


revision = "0006_swipes_unique_constraint"
down_revision = "0005_tmdb_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("swipes", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_swipes_room_movie_user_direction",
            ["room_code", "movie_id", "user_id", "direction", "session_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("swipes", schema=None) as batch_op:
        batch_op.drop_constraint("uq_swipes_room_movie_user_direction", type_="unique")
