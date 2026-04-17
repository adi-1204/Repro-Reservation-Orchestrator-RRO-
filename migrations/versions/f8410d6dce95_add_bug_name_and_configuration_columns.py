"""add bug_name and configuration columns

Revision ID: f8410d6dce95
Revises: b510fcfa58f3
Create Date: 2026-03-18 17:10:22.598708

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8410d6dce95'
down_revision = 'b510fcfa58f3'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('Bugs', sa.Column('bug_name', sa.String(length=255), nullable=True))
    op.add_column('Bug_Tests', sa.Column('configuration', sa.String(length=50), nullable=True))


def downgrade():
    op.drop_column('Bug_Tests', 'configuration')
    op.drop_column('Bugs', 'bug_name')
