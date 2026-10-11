"""accounts.ml_scores: churn/expansion scores written by the AI service's ML model

Revision ID: 0007
Revises: 0006
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts", sa.Column("ml_scores", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts", "ml_scores")
