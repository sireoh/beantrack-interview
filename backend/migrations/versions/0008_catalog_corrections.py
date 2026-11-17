"""Catalogue corrections (admin-reviewed), personal TV overrides, and the custom display toggle."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "show_corrections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("imdb_id", sa.String(length=16), nullable=False),
        sa.Column("submitted_by", sa.String(length=32), nullable=False),
        sa.Column("new_title", sa.String(length=255), nullable=True),
        sa.Column("new_image", sa.String(length=512), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                name="correction_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_by", sa.String(length=32), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "new_title IS NOT NULL OR new_image IS NOT NULL",
            name=op.f("ck_show_corrections_title_or_image"),
        ),
        sa.ForeignKeyConstraint(
            ["imdb_id"],
            ["tvshows.imdb"],
            name=op.f("fk_show_corrections_imdb_id_tvshows"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"],
            ["users.discord_id"],
            name=op.f("fk_show_corrections_submitted_by_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by"],
            ["users.discord_id"],
            name=op.f("fk_show_corrections_reviewed_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_show_corrections")),
    )
    op.create_index(op.f("ix_show_corrections_imdb_id"), "show_corrections", ["imdb_id"])
    op.create_index(
        op.f("ix_show_corrections_submitted_by"), "show_corrections", ["submitted_by"]
    )
    op.create_index(op.f("ix_show_corrections_status"), "show_corrections", ["status"])
    # One pending correction per user per show; resubmitting updates that row instead.
    op.create_index(
        "uq_show_corrections_one_pending",
        "show_corrections",
        ["submitted_by", "imdb_id"],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "tv_overrides",
        sa.Column("discord_id", sa.String(length=32), nullable=False),
        sa.Column("imdb_id", sa.String(length=16), nullable=False),
        sa.Column("custom_title", sa.String(length=255), nullable=True),
        sa.Column("custom_image", sa.String(length=512), nullable=True),
        sa.ForeignKeyConstraint(
            ["discord_id"],
            ["users.discord_id"],
            name=op.f("fk_tv_overrides_discord_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["imdb_id"],
            ["tvshows.imdb"],
            name=op.f("fk_tv_overrides_imdb_id_tvshows"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("discord_id", "imdb_id", name=op.f("pk_tv_overrides")),
    )

    # Existing users get the default (on) through the server default.
    op.add_column(
        "users",
        sa.Column(
            "custom_display_enabled", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
    )


def downgrade() -> None:
    # Native DROP COLUMN (SQLite >= 3.35), not batch mode: a batch rebuild drops the old
    # `users` table with foreign_keys=ON, which cascade-deletes every user's lists and sessions.
    op.execute("ALTER TABLE users DROP COLUMN custom_display_enabled")
    op.drop_table("tv_overrides")
    op.drop_index("uq_show_corrections_one_pending", table_name="show_corrections")
    op.drop_index(op.f("ix_show_corrections_status"), table_name="show_corrections")
    op.drop_index(op.f("ix_show_corrections_submitted_by"), table_name="show_corrections")
    op.drop_index(op.f("ix_show_corrections_imdb_id"), table_name="show_corrections")
    op.drop_table("show_corrections")
