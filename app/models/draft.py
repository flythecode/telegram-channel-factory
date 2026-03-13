from sqlalchemy import Enum as SqlEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.enums import DraftStatus




class Draft(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "drafts"

    content_task_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_tasks.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    generation_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[DraftStatus] = mapped_column(
        SqlEnum(DraftStatus, name="draft_status", values_callable=lambda e: [m.value for m in e]), nullable=False, default=DraftStatus.CREATED
    )

    content_task = relationship("ContentTask", back_populates="drafts")
    publications = relationship("Publication", back_populates="draft", cascade="all, delete-orphan")
