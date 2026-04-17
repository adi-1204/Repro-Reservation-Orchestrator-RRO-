"""add run_parameters table

Revision ID: d4b7c8e1f2a3
Revises: 90d9113e2475, c7e8f9a2d3b4
Create Date: 2026-04-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4b7c8e1f2a3'
down_revision = ('90d9113e2475', 'c7e8f9a2d3b4')
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()
    table_names_lc = {name.lower(): name for name in table_names}
    run_params_table_name = table_names_lc.get('run_parameters')

    if run_params_table_name is None:
        op.create_table(
            'Run_Parameters',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('bug_id', sa.Integer(), nullable=False),
            sa.Column('run_mode', sa.Enum('run_tests', 'config_and_execute'), nullable=False),
            sa.Column('test_name', sa.String(length=200), nullable=True),
            sa.Column('run_type', sa.Enum('quick', 'comprehensive'), nullable=False),
            sa.Column('workflow', sa.String(length=200), nullable=True),
            sa.Column('run_count', sa.Integer(), nullable=True),
            sa.Column('provision_setup', sa.Text(), nullable=True),
            sa.Column('do_checkout_update', sa.Boolean(), server_default=sa.text('0'), nullable=False),
            sa.Column('submitted_by', sa.Integer(), nullable=True),
            sa.Column('submitted_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
            sa.Column('status', sa.Enum('queued', 'running', 'completed', 'failed'), server_default='queued', nullable=False),
            sa.ForeignKeyConstraint(['bug_id'], ['Bugs.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['submitted_by'], ['Users.ID'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )
        run_params_table_name = 'Run_Parameters'

    existing_indexes = {idx['name'] for idx in inspector.get_indexes(run_params_table_name)}
    if 'idx_run_parameters_bug' not in existing_indexes:
        op.create_index('idx_run_parameters_bug', 'Run_Parameters', ['bug_id'], unique=False)
    if 'idx_run_parameters_submitted_by' not in existing_indexes:
        op.create_index('idx_run_parameters_submitted_by', 'Run_Parameters', ['submitted_by'], unique=False)


def downgrade():
    op.drop_index('idx_run_parameters_submitted_by', table_name='Run_Parameters')
    op.drop_index('idx_run_parameters_bug', table_name='Run_Parameters')
    op.drop_table('Run_Parameters')
