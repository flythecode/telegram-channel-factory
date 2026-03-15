"""add generation jobs

Revision ID: 20260314_1625
Revises: 20260314_1605
Create Date: 2026-03-14 16:25:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '20260314_1625'
down_revision = '20260314_1605'
branch_labels = None
depends_on = None


generation_job_status = postgresql.ENUM('queued', 'processing', 'succeeded', 'failed', name='generation_job_status', create_type=False)
generation_job_operation = postgresql.ENUM('create_draft', 'regenerate_draft', 'rewrite_draft', 'generate_content_plan', name='generation_job_operation', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    generation_job_status.create(bind, checkfirst=True)
    generation_job_operation.create(bind, checkfirst=True)
    op.create_table(
        'generation_jobs',
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('content_task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('draft_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('content_plan_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('client_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('operation', generation_job_operation, nullable=False),
        sa.Column('status', generation_job_status, nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('lease_token', sa.String(length=64), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('result_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('queued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['client_account_id'], ['client_accounts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['content_plan_id'], ['content_plans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['content_task_id'], ['content_tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['draft_id'], ['drafts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('generation_jobs')
    generation_job_operation.drop(op.get_bind(), checkfirst=True)
    generation_job_status.drop(op.get_bind(), checkfirst=True)
