"""agent plan patches and version history

Revision ID: 0006_agent_plan_patches
Revises: 0005_local_knowledge_base
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_agent_plan_patches"
down_revision = "0005_local_knowledge_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("video_tasks.task_id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_patch_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("task_id", "version", name="uq_plan_versions_task_version"),
    )
    op.create_index("ix_plan_versions_task_id", "plan_versions", ["task_id"])
    op.create_table(
        "agent_plan_patches",
        sa.Column("patch_id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("video_tasks.task_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("instruction_sha256", sa.String(64), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("patch_json", sa.JSON(), nullable=False),
        sa.Column("approved_operation_ids_json", sa.JSON(), nullable=False),
        sa.Column("resulting_version", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.String(240), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_plan_patches_task_id", "agent_plan_patches", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_plan_patches_task_id", table_name="agent_plan_patches")
    op.drop_table("agent_plan_patches")
    op.drop_index("ix_plan_versions_task_id", table_name="plan_versions")
    op.drop_table("plan_versions")
