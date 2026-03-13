from sqlalchemy import Boolean, Enum as SqlEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.enums import AgentRole


class AgentProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_profiles"

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telegram_channels.id", ondelete="SET NULL"), nullable=True
    )
    preset_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[AgentRole] = mapped_column(
        SqlEnum(AgentRole, name="agent_role", values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    style_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    custom_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    project = relationship("Project", back_populates="agent_profiles")
    telegram_channel = relationship("TelegramChannel")
