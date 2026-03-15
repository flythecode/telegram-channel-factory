from datetime import datetime

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.enums import GenerationJobOperation, GenerationJobStatus


class GenerationJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "generation_jobs"

    project_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    content_task_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_tasks.id", ondelete="CASCADE"), nullable=True
    )
    draft_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id", ondelete="CASCADE"), nullable=True
    )
    content_plan_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_plans.id", ondelete="CASCADE"), nullable=True
    )
    client_account_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_accounts.id", ondelete="SET NULL"), nullable=True
    )
    operation: Mapped[GenerationJobOperation] = mapped_column(
        SqlEnum(GenerationJobOperation, name="generation_job_operation", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    status: Mapped[GenerationJobStatus] = mapped_column(
        SqlEnum(GenerationJobStatus, name="generation_job_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=GenerationJobStatus.QUEUED,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    lease_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    result_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project")
    content_task = relationship("ContentTask")
    draft = relationship("Draft")
    content_plan = relationship("ContentPlan")
    client_account = relationship("ClientAccount")
