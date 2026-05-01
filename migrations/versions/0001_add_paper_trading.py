"""climate phase 1: drop edge_threshold, add paper_trading

Revision ID: 0001_climate_phase1
Revises:
Create Date: 2026-05-01

- Drop unused `edge_threshold` column from settings (DecisionEngine uses
  STRENGTH_THRESHOLDS instead; the value was never read).
- Add `paper_trading` boolean column (default True) to gate live execution.
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_climate_phase1"
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
        # Drop edge_threshold if it exists (best-effort — fresh DBs won't have it).
        try:
            batch_op.drop_column("edge_threshold")
        except Exception:
            pass


def downgrade() -> None:
    with op.batch_alter_table("settings") as batch_op:
        batch_op.drop_column("paper_trading")
        batch_op.add_column(
            sa.Column(
                "edge_threshold",
                sa.Float(),
                nullable=False,
                server_default="0.20",
            )
        )
