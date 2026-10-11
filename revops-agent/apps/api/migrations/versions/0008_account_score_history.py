"""account_score_history: an account's risk and expansion score per day (Help assistant windows)

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

from app.db.rls import apply_tenant_rls, drop_tenant_rls

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "account_score_history",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("risk_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("expansion_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_account_score_history_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_account_score_history_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_account_score_history")),
        sa.UniqueConstraint("org_id", "account_id", "day", name="uq_account_score_history_day"),
    )
    op.create_index(
        op.f("ix_account_score_history_org_id"), "account_score_history", ["org_id"], unique=False
    )
    op.create_index(
        "ix_account_score_history_org_id_day", "account_score_history", ["org_id", "day"]
    )
    apply_tenant_rls(op, "account_score_history")


def downgrade() -> None:
    drop_tenant_rls(op, "account_score_history")
    op.drop_index("ix_account_score_history_org_id_day", table_name="account_score_history")
    op.drop_index(op.f("ix_account_score_history_org_id"), table_name="account_score_history")
    op.drop_table("account_score_history")
