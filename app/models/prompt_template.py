from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PromptTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "prompt_templates"

    project_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[str] = mapped_column(String(50), nullable=False, default="global")
    role_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    style_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    project = relationship("Project")
