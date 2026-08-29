"""Add project-local knowledge documents and chunks.

Revision ID: 0005_local_knowledge_base
Revises: 0004_agent_approval
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_local_knowledge_base"
down_revision = "0004_agent_approval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("document_id", sa.String(length=40), primary_key=True),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_path", sa.String(length=320), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("summary", sa.String(length=400), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("index_version", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_table(
        "knowledge_chunks",
        sa.Column("chunk_id", sa.String(length=48), primary_key=True),
        sa.Column(
            "document_id", sa.String(length=40),
            sa.ForeignKey("knowledge_documents.document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("embedding_json", sa.JSON(), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), nullable=False),
        sa.Column("index_version", sa.String(length=64), nullable=False),
        sa.UniqueConstraint(
            "document_id", "ordinal", name="uq_knowledge_chunks_document_ordinal"
        ),
    )
    op.create_index(
        "ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
