from sqlalchemy import Boolean, Enum as SqlEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.enums import PublishMode


class TelegramChannel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "telegram_channels"

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    channel_title: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    bot_is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_post_messages: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    connection_notes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    publish_mode: Mapped[PublishMode] = mapped_column(
        SqlEnum(PublishMode, name="publish_mode", values_callable=lambda e: [m.value for m in e]), nullable=False, default=PublishMode.MANUAL
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project = relationship("Project", back_populates="telegram_channels")
    publications = relationship("Publication", back_populates="telegram_channel")
