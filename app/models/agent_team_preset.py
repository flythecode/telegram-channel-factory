from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentTeamPreset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_team_presets"

    code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_count: Mapped[int] = mapped_column(Integer, nullable=False)
    roles_json: Mapped[list | dict] = mapped_column(JSONB, nullable=False)
    is_recommended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
