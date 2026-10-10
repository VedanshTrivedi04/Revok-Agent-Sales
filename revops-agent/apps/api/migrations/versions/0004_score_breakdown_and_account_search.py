"""findings.score_breakdown column and trigram search index on accounts.name

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "findings",
        sa.Column("score_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # Existing rows kept the breakdown inside previous_snapshot (Phase 3); move it.
    op.execute(
        """
        UPDATE findings
           SET score_breakdown = previous_snapshot -> 'score_breakdown',
               previous_snapshot = NULLIF(previous_snapshot - 'score_breakdown', '{}'::jsonb)
         WHERE previous_snapshot ? 'score_breakdown'
        """
    )
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_accounts_name_trgm ON accounts USING gin (lower(name) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_accounts_name_trgm")
    op.drop_column("findings", "score_breakdown")
