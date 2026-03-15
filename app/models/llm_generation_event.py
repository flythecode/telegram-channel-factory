from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LLMGenerationEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "llm_generation_events"

    client_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_accounts.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    telegram_channel_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telegram_channels.id", ondelete="SET NULL"), nullable=True
    )
    content_task_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_tasks.id", ondelete="SET NULL"), nullable=True
    )
    draft_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id", ondelete="SET NULL"), nullable=True
    )
    operation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="succeeded")
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    client = relationship("ClientAccount")
    project = relationship("Project", back_populates="llm_generation_events")
    telegram_channel = relationship("TelegramChannel", back_populates="llm_generation_events")
    content_task = relationship("ContentTask", back_populates="llm_generation_events")
    draft = relationship("Draft", back_populates="llm_generation_events")

    @property
    def channel_id(self):
        return self.telegram_channel_id

    @property
    def task_id(self):
        return self.content_task_id
