"""add comments ml_analysis extend bug_tests

Revision ID: b510fcfa58f3
Revises: 8a4d7b2c1e90
Create Date: 2026-03-16 21:39:52.450359

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b510fcfa58f3'
down_revision = '8a4d7b2c1e90'
branch_labels = None
depends_on = None


def upgrade():
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
    op.add_column('Bug_Tests', sa.Column('station_name', sa.String(length=100), nullable=True))

    op.create_table(
        'Bug_Comments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('bug_id', sa.Integer(), nullable=True),
        sa.Column('comment_bugzilla_id', sa.Integer(), nullable=True),
        sa.Column('creator', sa.String(length=100), nullable=True),
        sa.Column('creation_time', sa.DateTime(), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['bug_id'], ['Bugs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('Bug_Comments', schema=None) as batch_op:
        batch_op.create_index('idx_bug', ['bug_id'], unique=False)

    op.create_table(
        'ML_Analysis',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('bug_id', sa.Integer(), nullable=True),
        sa.Column('repro_actions', sa.Text(), nullable=True),
        sa.Column('config_changes', sa.Text(), nullable=True),
        sa.Column('repro_readiness', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('generated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['bug_id'], ['Bugs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bug_id')
    )
    with op.batch_alter_table('ML_Analysis', schema=None) as batch_op:
        batch_op.create_index('idx_bug', ['bug_id'], unique=False)


def downgrade():
    with op.batch_alter_table('ML_Analysis', schema=None) as batch_op:
        batch_op.drop_index('idx_bug')
    op.drop_table('ML_Analysis')

    with op.batch_alter_table('Bug_Comments', schema=None) as batch_op:
        batch_op.drop_index('idx_bug')
    op.drop_table('Bug_Comments')

    op.drop_column('Bug_Tests', 'station_name')
    op.drop_column('Bug_Tests', 'signature')
    op.drop_column('Bug_Tests', 'odin_link')
    op.drop_column('Bug_Tests', 'nfs_path')
    op.drop_column('Bug_Tests', 'build_version')
    op.drop_column('Bug_Tests', 'failure_type')
    op.drop_column('Bug_Tests', 'number_of_nodes')
    op.drop_column('Bug_Tests', 'controller_types')
    op.drop_column('Bug_Tests', 'execution_end')
    op.drop_column('Bug_Tests', 'execution_start')
    op.drop_column('Bug_Tests', 'test_ring_name')
    op.drop_column('Bug_Tests', 'test_plan_name')
