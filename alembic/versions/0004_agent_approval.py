"""Persist Agent approval policy and human decisions.

Revision ID: 0004_agent_approval
Revises: 0003_agent_director_instruction
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_agent_approval"
down_revision = "0003_agent_director_instruction"
branch_labels = None
depends_on = None


_OLD_STATUS = sa.Enum(
    "PENDING", "PROCESSING", "RENDERING", "COMPLETED", "FAILED", "CANCELLED",
    name="taskstatus", native_enum=False,
)
_NEW_STATUS = sa.Enum(
    "PENDING", "PROCESSING", "RENDERING", "AWAITING_APPROVAL",
    "COMPLETED", "FAILED", "CANCELLED", "REJECTED",
    name="taskstatus", native_enum=False,
)


def upgrade() -> None:
    with op.batch_alter_table("video_tasks") as batch_op:
        batch_op.alter_column("status", existing_type=_OLD_STATUS, type_=_NEW_STATUS, nullable=False)
        batch_op.add_column(
            sa.Column(
                "approval_policy",
                sa.Enum("NEVER", "ON_RISK", "ALWAYS", name="approvalpolicy", native_enum=False),
                nullable=False,
                server_default="NEVER",
            )
        )
    op.create_table(
        "agent_approvals",
        sa.Column("task_id", sa.String(length=36), sa.ForeignKey("video_tasks.task_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("policy", sa.String(length=24), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("candidate_plan_json", sa.JSON(), nullable=True),
        sa.Column("violations_json", sa.JSON(), nullable=False),
        sa.Column("decision_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("agent_approvals")
    with op.batch_alter_table("video_tasks") as batch_op:
        batch_op.drop_column("approval_policy")
        batch_op.alter_column("status", existing_type=_NEW_STATUS, type_=_OLD_STATUS, nullable=False)
