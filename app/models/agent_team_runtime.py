from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentTeamRuntime(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_team_runtimes"
    __table_args__ = (
        UniqueConstraint("project_id", "channel_id", name="uq_agent_team_runtimes_project_channel"),
    )

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telegram_channels.id", ondelete="CASCADE"), nullable=True
    )
    client_account_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_accounts.id", ondelete="SET NULL"), nullable=True
    )
    runtime_scope: Mapped[str] = mapped_column(String(50), nullable=False, default="project")
    runtime_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    preset_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="single-pass")
    agent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    settings_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    config_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project = relationship("Project", back_populates="agent_team_runtimes")
    telegram_channel = relationship("TelegramChannel", back_populates="agent_team_runtimes")
    client_account = relationship("ClientAccount")
