"""add content_plan summary for llm-generated plans

Revision ID: 20260314_1605
Revises: 20260314_1515
Create Date: 2026-03-14 16:05:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260314_1605"
down_revision = "20260314_1515"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('content_plans', sa.Column('summary', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('content_plans', 'summary')
