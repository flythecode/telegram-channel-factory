from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Workspace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workspaces"

    owner_user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    owner_user = relationship(
        "User",
        back_populates="owned_workspaces",
        foreign_keys=[owner_user_id],
    )
    created_by_user = relationship(
        "User",
        back_populates="workspaces",
        foreign_keys=[created_by_user_id],
    )
    projects = relationship("Project", back_populates="workspace", cascade="all, delete-orphan")
