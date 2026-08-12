"""Persist bounded Agent director instructions.

Revision ID: 0003_agent_director_instruction
Revises: 0002_agent_workflow_persistence
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_agent_director_instruction"
down_revision = "0002_agent_workflow_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("video_tasks") as batch_op:
        batch_op.add_column(sa.Column("director_instruction", sa.String(length=2000), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("video_tasks") as batch_op:
        batch_op.drop_column("director_instruction")
