from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TaskStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    RENDERING = "rendering"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class WorkflowMode(StrEnum):
    STANDARD = "standard"
    AGENT = "agent"


class ApprovalPolicy(StrEnum):
    NEVER = "never"
    ON_RISK = "on_risk"
    ALWAYS = "always"


class VideoTask(Base):
    __tablename__ = "video_tasks"

    task_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, native_enum=False), nullable=False)
    workflow_mode: Mapped[WorkflowMode] = mapped_column(
        Enum(WorkflowMode, native_enum=False), default=WorkflowMode.STANDARD, server_default="STANDARD", nullable=False
    )
    processing_profile: Mapped[str] = mapped_column(String(32), default="configured", server_default="configured", nullable=False)
    media_provider: Mapped[str] = mapped_column(String(64), default="mock", server_default="mock", nullable=False)
    director_instruction: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    approval_policy: Mapped[ApprovalPolicy] = mapped_column(
        Enum(ApprovalPolicy, native_enum=False),
        default=ApprovalPolicy.NEVER,
        server_default="NEVER",
        nullable=False,
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    transcript_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    plan_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    events: Mapped[list["TaskEvent"]] = relationship(back_populates="task", cascade="all, delete-orphan")
    approval: Mapped["AgentApproval | None"] = relationship(
        back_populates="task", cascade="all, delete-orphan", uselist=False
    )


class TaskEvent(Base):
    __tablename__ = "task_events"
    __table_args__ = (UniqueConstraint("task_id", "dedupe_key", name="uq_task_events_task_id_dedupe_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("video_tasks.task_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    message: Mapped[str] = mapped_column(String(256), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    dedupe_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    task: Mapped[VideoTask] = relationship(back_populates="events")


class AgentApproval(Base):
    __tablename__ = "agent_approvals"

    task_id: Mapped[str] = mapped_column(
        ForeignKey("video_tasks.task_id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    policy: Mapped[str] = mapped_column(String(24), nullable=False)
    reasons_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    candidate_plan_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    violations_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    decision_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    task: Mapped[VideoTask] = relationship(back_populates="approval")
