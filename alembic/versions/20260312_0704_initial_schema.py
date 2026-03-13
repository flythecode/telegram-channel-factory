"""initial schema

Revision ID: 20260312_0704
Revises: None
Create Date: 2026-03-12 07:04:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260312_0704"
down_revision = None
branch_labels = None
depends_on = None


project_status = postgresql.ENUM("active", "paused", "archived", name="project_status", create_type=False)
operation_mode = postgresql.ENUM("manual", "semi_auto", "auto", name="operation_mode", create_type=False)
publish_mode = postgresql.ENUM("manual", "scheduled", "auto", name="publish_mode", create_type=False)
agent_role = postgresql.ENUM(
    "strategist",
    "researcher",
    "writer",
    "editor",
    "fact_checker",
    "publisher",
    name="agent_role",
    create_type=False,
)
content_plan_period = postgresql.ENUM("week", "month", name="content_plan_period", create_type=False)
content_task_status = postgresql.ENUM(
    "pending",
    "in_progress",
    "drafted",
    "awaiting_approval",
    "approved",
    "rejected",
    "scheduled",
    "published",
    "failed",
    name="content_task_status",
    create_type=False,
)
draft_status = postgresql.ENUM(
    "created",
    "edited",
    "approved",
    "rejected",
    "published",
    name="draft_status",
    create_type=False,
)
publication_status = postgresql.ENUM(
    "queued",
    "sending",
    "sent",
    "failed",
    "canceled",
    name="publication_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    project_status.create(bind, checkfirst=True)
    operation_mode.create(bind, checkfirst=True)
    publish_mode.create(bind, checkfirst=True)
    agent_role.create(bind, checkfirst=True)
    content_plan_period.create(bind, checkfirst=True)
    content_task_status.create(bind, checkfirst=True)
    draft_status.create(bind, checkfirst=True)
    publication_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("telegram_user_id", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("telegram_user_id"),
    )

    op.create_table(
        "workspaces",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "projects",
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("niche", sa.String(length=255), nullable=True),
        sa.Column("language", sa.String(length=32), nullable=False),
        sa.Column("tone_of_voice", sa.Text(), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("content_format", sa.String(length=100), nullable=True),
        sa.Column("posting_frequency", sa.String(length=100), nullable=True),
        sa.Column("operation_mode", operation_mode, nullable=False),
        sa.Column("content_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", project_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "telegram_channels",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_title", sa.String(length=255), nullable=False),
        sa.Column("channel_username", sa.String(length=255), nullable=True),
        sa.Column("channel_id", sa.String(length=255), nullable=True),
        sa.Column("bot_is_admin", sa.Boolean(), nullable=False),
        sa.Column("can_post_messages", sa.Boolean(), nullable=False),
        sa.Column("is_connected", sa.Boolean(), nullable=False),
        sa.Column("connection_notes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("publish_mode", publish_mode, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id"),
    )

    op.create_table(
        "agent_profiles",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("preset_code", sa.String(length=100), nullable=True),
        sa.Column("role", agent_role, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("style_prompt", sa.Text(), nullable=True),
        sa.Column("custom_prompt", sa.Text(), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["telegram_channels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "agent_team_presets",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("agent_count", sa.Integer(), nullable=False),
        sa.Column("roles_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_recommended", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "prompt_templates",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False),
        sa.Column("role_code", sa.String(length=100), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("style_prompt", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "project_config_versions",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_events",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "content_plans",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_type", content_plan_period, nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("generated_by", sa.String(length=255), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "content_tasks",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("format", sa.String(length=100), nullable=True),
        sa.Column("angle", sa.Text(), nullable=True),
        sa.Column("brief", sa.Text(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", content_task_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["content_plan_id"], ["content_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "drafts",
        sa.Column("content_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_notes", sa.Text(), nullable=True),
        sa.Column("created_by_agent", sa.String(length=255), nullable=True),
        sa.Column("generation_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", draft_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["content_task_id"], ["content_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "publications",
        sa.Column("draft_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_message_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("status", publication_status, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["draft_id"], ["drafts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["telegram_channel_id"], ["telegram_channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("publications")
    op.drop_table("drafts")
    op.drop_table("content_tasks")
    op.drop_table("content_plans")
    op.drop_table("audit_events")
    op.drop_table("project_config_versions")
    op.drop_table("prompt_templates")
    op.drop_table("agent_team_presets")
    op.drop_table("agent_profiles")
    op.drop_table("telegram_channels")
    op.drop_table("projects")
    op.drop_table("workspaces")
    op.drop_table("users")

    bind = op.get_bind()
    publication_status.drop(bind, checkfirst=True)
    draft_status.drop(bind, checkfirst=True)
    content_task_status.drop(bind, checkfirst=True)
    content_plan_period.drop(bind, checkfirst=True)
    agent_role.drop(bind, checkfirst=True)
    publish_mode.drop(bind, checkfirst=True)
    operation_mode.drop(bind, checkfirst=True)
    project_status.drop(bind, checkfirst=True)
