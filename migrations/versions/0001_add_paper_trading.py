"""add paper_trading flag to settings

Revision ID: 0001_paper_trading
Revises:
Create Date: 2026-05-01

"""
from alembic import op
import sqlalchemy as sa


revision = "0001_paper_trading"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "paper_trading",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("settings") as batch_op:
        batch_op.drop_column("paper_trading")
