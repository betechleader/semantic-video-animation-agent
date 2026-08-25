"""Persist agent workflow configuration and deduplicated task events."""

from alembic import op
import sqlalchemy as sa

revision = "0002_agent_workflow_persistence"
down_revision = "0001_task_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("video_tasks") as batch_op:
        batch_op.add_column(
            sa.Column(
                "workflow_mode",
                sa.Enum("STANDARD", "AGENT", name="workflowmode", native_enum=False),
                nullable=False,
                server_default="STANDARD",
            )
        )
        batch_op.add_column(
            sa.Column("processing_profile", sa.String(length=32), nullable=False, server_default="configured")
        )
        batch_op.add_column(sa.Column("media_provider", sa.String(length=64), nullable=False, server_default="mock"))

    with op.batch_alter_table("task_events") as batch_op:
        batch_op.add_column(sa.Column("dedupe_key", sa.String(length=160), nullable=True))
        batch_op.create_unique_constraint(
            "uq_task_events_task_id_dedupe_key",
            ["task_id", "dedupe_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("task_events") as batch_op:
        batch_op.drop_constraint("uq_task_events_task_id_dedupe_key", type_="unique")
        batch_op.drop_column("dedupe_key")

    with op.batch_alter_table("video_tasks") as batch_op:
        batch_op.drop_column("media_provider")
        batch_op.drop_column("processing_profile")
        batch_op.drop_column("workflow_mode")
