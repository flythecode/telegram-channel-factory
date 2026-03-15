from datetime import datetime

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.enums import ContentTaskStatus


class ContentTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "content_tasks"

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    content_plan_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_plans.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[str | None] = mapped_column(String(100), nullable=True)
    angle: Mapped[str | None] = mapped_column(Text, nullable=True)
    brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generation_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ContentTaskStatus] = mapped_column(
        SqlEnum(ContentTaskStatus, name="content_task_status", values_callable=lambda e: [m.value for m in e]), nullable=False, default=ContentTaskStatus.PENDING
    )

    project = relationship("Project", back_populates="content_tasks")
    content_plan = relationship("ContentPlan", back_populates="content_tasks")
    drafts = relationship("Draft", back_populates="content_task", cascade="all, delete-orphan")
    llm_generation_events = relationship("LLMGenerationEvent", back_populates="content_task")
