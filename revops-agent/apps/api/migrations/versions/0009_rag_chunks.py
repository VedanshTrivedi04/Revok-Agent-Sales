"""rag_chunks: passages of a tenant's records with their embedding (Riddhi's retrieval index)

Revision ID: 0009
Revises: 0008
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.db.rls import apply_tenant_rls, drop_tenant_rls

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

HNSW = "ix_rag_chunks_embedding_hnsw"


def upgrade() -> None:
    op.create_table(
        "rag_chunks",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.SmallInteger(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("occurred_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("embedding", postgresql.ARRAY(sa.REAL()), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
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
        sa.CheckConstraint(
            "source_type IN ('finding', 'card', 'event')",
            name=op.f("ck_rag_chunks_source_type_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_rag_chunks_account_id_accounts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_rag_chunks_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rag_chunks")),
        sa.UniqueConstraint(
            "org_id", "source_type", "source_id", "seq", name="uq_rag_chunks_source_seq"
        ),
    )
    op.create_index(op.f("ix_rag_chunks_org_id"), "rag_chunks", ["org_id"], unique=False)
    op.create_index("ix_rag_chunks_org_id_account_id", "rag_chunks", ["org_id", "account_id"])
    apply_tenant_rls(op, "rag_chunks")

    # Similarity search runs in pgvector where the server offers it (Neon, Supabase, the pgvector
    # images). On a plain Postgres the table still works and the service ranks in Python.
    has_pgvector = (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"))
        .scalar()
    )
    if has_pgvector:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute(
            f"CREATE INDEX {HNSW} ON rag_chunks "
            "USING hnsw ((embedding::vector(768)) vector_cosine_ops)"
        )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {HNSW}")
    drop_tenant_rls(op, "rag_chunks")
    op.drop_index("ix_rag_chunks_org_id_account_id", table_name="rag_chunks")
    op.drop_index(op.f("ix_rag_chunks_org_id"), table_name="rag_chunks")
    op.drop_table("rag_chunks")
