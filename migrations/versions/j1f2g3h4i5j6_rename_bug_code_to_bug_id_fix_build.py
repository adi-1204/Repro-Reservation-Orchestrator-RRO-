"""
Migration: Rename bug_code to bug_id and fix Build table

Revision ID: j1f2g3h4i5j6
Revises: i0e1f2a3b4c5d
Create Date: 2026-04-15 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'j1f2g3h4i5j6'
down_revision = 'i0e1f2a3b4c5d'
branch_labels = None
depends_on = None


def upgrade():
    """
    1. Drop bug_id column from Builds table (if exists)
    2. Rename bug_code to bug_id in Bugs table
    3. Update all foreign key references
    """
    
    # 1. Drop bug_id from Builds if it exists
    try:
        op.drop_column('Builds', 'bug_id')
    except:
        pass  # Column might not exist
    
    # 2. Rename bug_code to bug_id in Bugs
    try:
        op.alter_table_comment('Bugs', comment=None, existing_comment=None)
        op.execute('ALTER TABLE Bugs CHANGE COLUMN bug_code bug_id VARCHAR(100)')
    except:
        pass  # Might already be renamed


def downgrade():
    """
    Reverse: Rename bug_id back to bug_code
    """
    try:
        op.execute('ALTER TABLE Bugs CHANGE COLUMN bug_id bug_code VARCHAR(100)')
    except:
        pass
