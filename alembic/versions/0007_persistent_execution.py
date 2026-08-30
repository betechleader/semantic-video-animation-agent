"""persistent execution jobs and worker heartbeats

Revision ID: 0007_persistent_execution
Revises: 0006_agent_plan_patches
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_persistent_execution"
down_revision = "0006_agent_plan_patches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_jobs",
        sa.Column("job_id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("video_tasks.task_id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("dedupe_key", sa.String(96), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("lease_owner", sa.String(96), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error_category", sa.String(96), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("task_id", "dedupe_key", name="uq_execution_jobs_task_dedupe"),
    )
    op.create_index("ix_execution_jobs_task_id", "execution_jobs", ["task_id"])
    op.create_index("ix_execution_jobs_status", "execution_jobs", ["status"])
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.String(96), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_worker_heartbeats_heartbeat_at", "worker_heartbeats", ["heartbeat_at"])


def downgrade() -> None:
    op.drop_index("ix_worker_heartbeats_heartbeat_at", table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")
    op.drop_index("ix_execution_jobs_status", table_name="execution_jobs")
    op.drop_index("ix_execution_jobs_task_id", table_name="execution_jobs")
    op.drop_table("execution_jobs")
