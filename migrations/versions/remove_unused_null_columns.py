"""remove unused null columns from Bug_Tests and add missing BugComment columns

Revision ID: f9b8c7d6e5a4
Revises: e5a1c3d9b7f0
Create Date: 2026-04-15 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f9b8c7d6e5a4'
down_revision = 'e5a1c3d9b7f0'
branch_labels = None
depends_on = None


def upgrade():
    """
    Remove unused NULL columns from Bug_Tests table that were never populated:
    - test_plan_name
    - test_ring_name
    - execution_start
    - execution_end
    - controller_types
    - number_of_nodes
    - failure_type
    - build_version (duplicate of build_id)
    - nfs_path
    - odin_link
    - signature
    
    Add missing columns to BugComment that are used by services:
    - comment_bugzilla_id (used for ordering in generate_ml_analysis.py)
    - creation_time (used in generate_ml_analysis.py and returned to UI)
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # ==========================================
    # Remove unused columns from Bug_Tests
    # ==========================================
    bug_tests_columns = {col['name'] for col in inspector.get_columns('Bug_Tests')}
    
    unused_columns = [
        'test_plan_name',
        'test_ring_name',
        'execution_start',
        'execution_end',
        'controller_types',
        'number_of_nodes',
        'failure_type',
        'build_version',
        'nfs_path',
        'odin_link',
        'signature'
    ]
    
    for col in unused_columns:
        if col in bug_tests_columns:
            op.drop_column('Bug_Tests', col)
    
    # ==========================================
    # Add missing columns to Bug_Comments
    # ==========================================
    bug_comments_columns = {col['name'] for col in inspector.get_columns('Bug_Comments')}
    
    if 'comment_bugzilla_id' not in bug_comments_columns:
        op.add_column('Bug_Comments', sa.Column('comment_bugzilla_id', sa.Integer(), nullable=True))
    
    if 'creation_time' not in bug_comments_columns:
        op.add_column('Bug_Comments', sa.Column('creation_time', sa.DateTime(), nullable=True))


def downgrade():
    """
    Restore the removed columns (blank/NULL).
    """
    # Re-add the removed columns
    op.add_column('Bug_Tests', sa.Column('test_plan_name', sa.String(length=200), nullable=True))
    op.add_column('Bug_Tests', sa.Column('test_ring_name', sa.String(length=100), nullable=True))
    op.add_column('Bug_Tests', sa.Column('execution_start', sa.DateTime(), nullable=True))
    op.add_column('Bug_Tests', sa.Column('execution_end', sa.DateTime(), nullable=True))
    op.add_column('Bug_Tests', sa.Column('controller_types', sa.String(length=100), nullable=True))
    op.add_column('Bug_Tests', sa.Column('number_of_nodes', sa.Integer(), nullable=True))
    op.add_column('Bug_Tests', sa.Column('failure_type', sa.String(length=50), nullable=True))
    op.add_column('Bug_Tests', sa.Column('build_version', sa.String(length=50), nullable=True))
    op.add_column('Bug_Tests', sa.Column('nfs_path', sa.String(length=500), nullable=True))
    op.add_column('Bug_Tests', sa.Column('odin_link', sa.String(length=500), nullable=True))
    op.add_column('Bug_Tests', sa.Column('signature', sa.String(length=500), nullable=True))
    
    # Remove added columns
    op.drop_column('Bug_Comments', 'comment_bugzilla_id')
    op.drop_column('Bug_Comments', 'creation_time')
