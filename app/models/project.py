from sqlalchemy import Enum as SqlEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.enums import OperationMode, ProjectStatus


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "projects"

    workspace_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    client_account_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("client_accounts.id", ondelete="SET NULL"), nullable=True
    )
    owner_user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    niche: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="ru")
    tone_of_voice: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_format: Mapped[str | None] = mapped_column(String(100), nullable=True)
    posting_frequency: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operation_mode: Mapped[OperationMode] = mapped_column(
        SqlEnum(OperationMode, name="operation_mode", values_callable=lambda e: [m.value for m in e]), nullable=False, default=OperationMode.MANUAL
    )
    content_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SqlEnum(ProjectStatus, name="project_status", values_callable=lambda e: [m.value for m in e]), nullable=False, default=ProjectStatus.ACTIVE
    )

    workspace = relationship("Workspace", back_populates="projects")
    client_account = relationship("ClientAccount", back_populates="projects")
    owner_user = relationship("User", back_populates="owned_projects", foreign_keys=[owner_user_id])
    created_by_user = relationship("User", back_populates="created_projects", foreign_keys=[created_by_user_id])
    telegram_channels = relationship("TelegramChannel", back_populates="project", cascade="all, delete-orphan")
    agent_profiles = relationship("AgentProfile", back_populates="project", cascade="all, delete-orphan")
    agent_team_runtimes = relationship("AgentTeamRuntime", back_populates="project", cascade="all, delete-orphan")
    content_plans = relationship("ContentPlan", back_populates="project", cascade="all, delete-orphan")
    content_tasks = relationship("ContentTask", back_populates="project", cascade="all, delete-orphan")
    llm_generation_events = relationship("LLMGenerationEvent", back_populates="project")
