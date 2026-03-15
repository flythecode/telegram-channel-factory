"""add generation metadata summary to tasks and publications

Revision ID: 20260314_1545
Revises: 20260314_1605
Create Date: 2026-03-14 15:45:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260314_1545'
down_revision = '20260314_1605'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('content_tasks', sa.Column('generation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('publications', sa.Column('generation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('publications', 'generation_metadata')
    op.drop_column('content_tasks', 'generation_metadata')
