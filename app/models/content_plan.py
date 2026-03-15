from datetime import date

from sqlalchemy import Date, Enum as SqlEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.enums import ContentPlanPeriod


class ContentPlan(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "content_plans"

    project_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    period_type: Mapped[ContentPlanPeriod] = mapped_column(
        SqlEnum(ContentPlanPeriod, name="content_plan_period", values_callable=lambda e: [m.value for m in e]), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False, default="generated")
    generated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    project = relationship("Project", back_populates="content_plans")
    content_tasks = relationship("ContentTask", back_populates="content_plan", cascade="all, delete-orphan")
