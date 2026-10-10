"""findings status priority index for Today performance

Revision ID: 0003
Revises: 0002
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_findings_org_id_status_priority_score",
        "findings",
        ["org_id", "status", sa.literal_column("priority_score DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_findings_org_id_status_priority_score", table_name="findings")
