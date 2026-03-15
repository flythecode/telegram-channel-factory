"""add agent_team_runtimes for project/channel execution context

Revision ID: 20260314_1515
Revises: 20260314_1500
Create Date: 2026-03-14 15:15:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260314_1515"
down_revision = "20260314_1500"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_team_runtimes",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("client_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("runtime_scope", sa.String(length=50), nullable=False, server_default="project"),
        sa.Column("runtime_key", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("preset_code", sa.String(length=100), nullable=True),
        sa.Column("generation_mode", sa.String(length=50), nullable=False, server_default="single-pass"),
        sa.Column("agent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settings_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("agent_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("runtime_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("config_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["telegram_channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_account_id"], ["client_accounts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("runtime_key"),
        sa.UniqueConstraint("project_id", "channel_id", name="uq_agent_team_runtimes_project_channel"),
    )
    op.create_index("ix_agent_team_runtimes_project_id", "agent_team_runtimes", ["project_id"])
    op.create_index("ix_agent_team_runtimes_channel_id", "agent_team_runtimes", ["channel_id"])
    op.create_index("ix_agent_team_runtimes_client_account_id", "agent_team_runtimes", ["client_account_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_team_runtimes_client_account_id", table_name="agent_team_runtimes")
    op.drop_index("ix_agent_team_runtimes_channel_id", table_name="agent_team_runtimes")
    op.drop_index("ix_agent_team_runtimes_project_id", table_name="agent_team_runtimes")
    op.drop_table("agent_team_runtimes")
