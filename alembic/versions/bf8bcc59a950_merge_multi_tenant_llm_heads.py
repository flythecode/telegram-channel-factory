"""merge multi-tenant llm heads

Revision ID: bf8bcc59a950
Revises: 20260314_1545, 20260314_1625
Create Date: 2026-03-14 22:50:39.866437
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bf8bcc59a950'
down_revision = ('20260314_1545', '20260314_1625')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
