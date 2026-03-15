"""add client_accounts and project subscription context

Revision ID: 20260314_1500
Revises: 20260314_1420
Create Date: 2026-03-14 15:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260314_1500"
down_revision = "20260314_1420"
branch_labels = None
depends_on = None

subscription_status = postgresql.ENUM("trial", "active", "past_due", "canceled", "suspended", name="subscription_status", create_type=False)
billing_cycle = postgresql.ENUM("monthly", "yearly", "custom", name="billing_cycle", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    subscription_status.create(bind, checkfirst=True)
    billing_cycle.create(bind, checkfirst=True)

    op.create_table(
        "client_accounts",
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workspace_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("billing_email", sa.String(length=255), nullable=True),
        sa.Column("external_billing_customer_id", sa.String(length=255), nullable=True),
        sa.Column("subscription_plan_code", sa.String(length=100), nullable=False, server_default="trial"),
        sa.Column("subscription_status", subscription_status, nullable=False, server_default="trial"),
        sa.Column("billing_cycle", billing_cycle, nullable=True),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seats_included", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_billing_customer_id"),
    )
    op.create_index("ix_client_accounts_owner_user_id", "client_accounts", ["owner_user_id"])
    op.create_index("ix_client_accounts_workspace_id", "client_accounts", ["workspace_id"])

    op.add_column("projects", sa.Column("client_account_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_projects_client_account_id", "projects", "client_accounts", ["client_account_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_projects_client_account_id", "projects", ["client_account_id"])

    op.execute(
        """
        INSERT INTO client_accounts (id, owner_user_id, workspace_id, name, billing_email, subscription_plan_code, subscription_status, settings, is_active)
        SELECT gen_random_uuid(), w.owner_user_id, w.id, COALESCE(NULLIF(w.name, ''), COALESCE(u.full_name, u.email, 'Client Account')), u.email, 'trial', 'trial',
               jsonb_build_object('backfilled_from', 'users_projects'), true
        FROM workspaces w
        JOIN users u ON u.id = w.owner_user_id
        WHERE NOT EXISTS (
            SELECT 1 FROM client_accounts ca WHERE ca.owner_user_id = w.owner_user_id AND (ca.workspace_id = w.id OR ca.workspace_id IS NULL)
        )
        """
    )

    op.execute(
        """
        UPDATE projects p
        SET client_account_id = ca.id
        FROM client_accounts ca
        WHERE p.owner_user_id = ca.owner_user_id
          AND (p.workspace_id = ca.workspace_id OR ca.workspace_id IS NULL)
          AND p.client_account_id IS NULL
        """
    )

    op.drop_constraint(op.f('llm_generation_events_client_id_fkey'), 'llm_generation_events', type_='foreignkey')
    op.create_foreign_key(
        'fk_llm_generation_events_client_id_client_accounts',
        'llm_generation_events',
        'client_accounts',
        ['client_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_llm_generation_events_client_id_client_accounts', 'llm_generation_events', type_='foreignkey')
    op.create_foreign_key(op.f('llm_generation_events_client_id_fkey'), 'llm_generation_events', 'users', ['client_id'], ['id'], ondelete='SET NULL')
    op.drop_index('ix_projects_client_account_id', table_name='projects')
    op.drop_constraint('fk_projects_client_account_id', 'projects', type_='foreignkey')
    op.drop_column('projects', 'client_account_id')
    op.drop_index('ix_client_accounts_workspace_id', table_name='client_accounts')
    op.drop_index('ix_client_accounts_owner_user_id', table_name='client_accounts')
    op.drop_table('client_accounts')
    billing_cycle.drop(op.get_bind(), checkfirst=True)
    subscription_status.drop(op.get_bind(), checkfirst=True)
