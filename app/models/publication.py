from datetime import datetime

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.enums import PublicationStatus


class Publication(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "publications"

    draft_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drafts.id", ondelete="CASCADE"), nullable=False
    )
    telegram_channel_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("telegram_channels.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    generation_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[PublicationStatus] = mapped_column(
        SqlEnum(PublicationStatus, name="publication_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=PublicationStatus.QUEUED,
    )

    draft = relationship("Draft", back_populates="publications")
    telegram_channel = relationship("TelegramChannel", back_populates="publications")
