"""Remove unused comment_bugzilla_id and populate creation_time

Revision ID: i0e1f2a3b4c5d
Revises: h1d0e9f8g7b6
Create Date: 2026-04-15 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


revision = 'i0e1f2a3b4c5d'
down_revision = 'h1d0e9f8g7b6'
branch_labels = None
depends_on = None


def upgrade():
    """
    Remove unused comment_bugzilla_id column and fix creation_time:
    1. Set default creation_time to CURRENT_TIMESTAMP for future inserts
    2. Populate existing NULL values with current timestamp
    3. Make creation_time NOT NULL
    4. Drop comment_bugzilla_id column (never used, always NULL)
    """
    # First, set all NULL creation_time to current timestamp
    op.execute(
        "UPDATE Bug_Comments SET creation_time = NOW() WHERE creation_time IS NULL"
    )
    
    # Make creation_time NOT NULL with server default for fresh inserts
    op.alter_column(
        'Bug_Comments',
        'creation_time',
        existing_type=sa.DateTime(),
        nullable=False,
        server_default=sa.func.now()
    )
    
    # Drop unused comment_bugzilla_id column
    op.drop_column('Bug_Comments', 'comment_bugzilla_id')


def downgrade():
    """
    Reverse: add comment_bugzilla_id back and revert creation_time to nullable
    """
    op.add_column(
        'Bug_Comments',
        sa.Column('comment_bugzilla_id', sa.Integer(), nullable=True)
    )
    
    op.alter_column(
        'Bug_Comments',
        'creation_time',
        existing_type=sa.DateTime(),
        nullable=True,
        server_default=None
    )
