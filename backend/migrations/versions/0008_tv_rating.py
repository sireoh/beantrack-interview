"""Store each user's personal 1-10 rating on their TV list entries."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_tvshows", sa.Column("rating", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user_tvshows") as batch:
        batch.drop_column("rating")
