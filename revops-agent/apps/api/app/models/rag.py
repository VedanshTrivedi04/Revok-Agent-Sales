"""Retrieval index for Riddhi: passages of a tenant's own records with their embedding.

The embedding is stored as `real[]` so the table exists on any Postgres. Where the server has
pgvector (see migration 0009) an HNSW index over `embedding::vector(768)` does the similarity
search; without it the service ranks in Python.
"""

from sqlalchemy import REAL, Index, SmallInteger, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.db.base import Base, IdMixin, TimestampMixin
from app.models._h import UUID, Mapped, datetime, enum_ck, mapped_column, tenant_fk, uuid_fk

RAG_SOURCES = ("finding", "card", "event")
EMBEDDING_DIM = 768


class RagChunk(Base, IdMixin, TimestampMixin):
    """One passage of one record. `source_id` is the finding, action card or event it was cut
    from; all passages of a record share `content_hash`, so a changed record is embedded again."""

    __tablename__ = "rag_chunks"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "source_type", "source_id", "seq", name="uq_rag_chunks_source_seq"
        ),
        enum_ck("source_type", RAG_SOURCES),
        Index("ix_rag_chunks_org_id_account_id", "org_id", "account_id"),
    )

    org_id: Mapped[UUID] = tenant_fk()
    account_id: Mapped[UUID | None] = uuid_fk("accounts.id", nullable=True)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    seq: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    embedding: Mapped[list[float]] = mapped_column(ARRAY(REAL), nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
