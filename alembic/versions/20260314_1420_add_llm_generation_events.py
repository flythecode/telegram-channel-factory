"""add llm_generation_events

Revision ID: 20260314_1420
Revises: 20260312_0704
Create Date: 2026-03-14 14:20:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260314_1420"
down_revision = "20260312_0704"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_generation_events",
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("telegram_channel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("content_task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("operation_type", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["content_task_id"], ["content_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["draft_id"], ["drafts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["telegram_channel_id"], ["telegram_channels.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_llm_generation_events_client_id", "llm_generation_events", ["client_id"])
    op.create_index("ix_llm_generation_events_project_id", "llm_generation_events", ["project_id"])
    op.create_index("ix_llm_generation_events_task_id", "llm_generation_events", ["content_task_id"])
    op.create_index("ix_llm_generation_events_draft_id", "llm_generation_events", ["draft_id"])
    op.create_index("ix_llm_generation_events_request_id", "llm_generation_events", ["request_id"])


def downgrade() -> None:
    op.drop_index("ix_llm_generation_events_request_id", table_name="llm_generation_events")
    op.drop_index("ix_llm_generation_events_client_id", table_name="llm_generation_events")
    op.drop_index("ix_llm_generation_events_draft_id", table_name="llm_generation_events")
    op.drop_index("ix_llm_generation_events_task_id", table_name="llm_generation_events")
    op.drop_index("ix_llm_generation_events_project_id", table_name="llm_generation_events")
    op.drop_table("llm_generation_events")
