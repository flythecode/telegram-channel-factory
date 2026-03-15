from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.utils.enums import BillingCycle, SubscriptionStatus


class ClientAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "client_accounts"

    owner_user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_billing_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    subscription_plan_code: Mapped[str] = mapped_column(String(100), nullable=False, default="trial")
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        SqlEnum(SubscriptionStatus, name="subscription_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=SubscriptionStatus.TRIAL,
    )
    billing_cycle: Mapped[BillingCycle | None] = mapped_column(
        SqlEnum(BillingCycle, name="billing_cycle", values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    seats_included: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    owner_user = relationship("User", back_populates="client_accounts", foreign_keys=[owner_user_id])
    workspace = relationship("Workspace", back_populates="client_accounts")
    projects = relationship("Project", back_populates="client_account")


    @property
    def access_flag(self) -> str:
        status_value = getattr(self.subscription_status, 'value', self.subscription_status)
        status_value = str(status_value or '').strip().lower()
        if status_value == 'trial':
            return 'trial'
        if status_value == 'active':
            return 'paid'
        return 'unpaid'
