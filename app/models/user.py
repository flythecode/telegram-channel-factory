from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    owned_workspaces = relationship(
        "Workspace",
        back_populates="owner_user",
        foreign_keys="Workspace.owner_user_id",
    )
    workspaces = relationship(
        "Workspace",
        back_populates="created_by_user",
        foreign_keys="Workspace.created_by_user_id",
    )
    owned_projects = relationship(
        "Project",
        back_populates="owner_user",
        foreign_keys="Project.owner_user_id",
    )
    created_projects = relationship(
        "Project",
        back_populates="created_by_user",
        foreign_keys="Project.created_by_user_id",
    )

    client_accounts = relationship(
        "ClientAccount",
        back_populates="owner_user",
        foreign_keys="ClientAccount.owner_user_id",
        cascade="all, delete-orphan",
    )
