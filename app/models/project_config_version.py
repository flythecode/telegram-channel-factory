from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectConfigVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "project_config_versions"

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    project = relationship("Project")
    created_by_user = relationship("User")
