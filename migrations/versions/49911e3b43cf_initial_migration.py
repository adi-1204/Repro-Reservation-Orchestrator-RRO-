"""initial migration

Revision ID: 49911e3b43cf
Revises: 
Create Date: 2026-03-10 21:39:24.375287

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '49911e3b43cf'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'Users',
        sa.Column('ID', sa.Integer(), nullable=False),
        sa.Column('First_Name', sa.String(length=10), nullable=False),
        sa.Column('Last_Name', sa.String(length=10), nullable=True),
        sa.Column('Email', sa.String(length=100), nullable=False),
        sa.Column('Password', sa.String(length=255), nullable=False),
        sa.Column('Role', sa.Enum('Engineer', 'Manager'), nullable=False),
        sa.PrimaryKeyConstraint('ID'),
        sa.UniqueConstraint('Email')
    )
    op.create_index('idx_role', 'Users', ['Role'], unique=False)
    op.create_index('idx_email', 'Users', ['Email'], unique=False)

    op.create_table(
        'Workgroup_Schema',
        sa.Column('ID', sa.Integer(), nullable=False),
        sa.Column('Name', sa.String(length=100), nullable=True),
        sa.Column('Release_Version', sa.String(length=10), nullable=False),
        sa.Column('Status', sa.Enum('Completed', 'Active'), server_default='Active', nullable=False),
        sa.Column('Manager_ID', sa.Integer(), nullable=True),
        sa.Column('Created_At', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['Manager_ID'], ['Users.ID'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('ID')
    )
    op.create_index('idx_manager', 'Workgroup_Schema', ['Manager_ID'], unique=False)
    op.create_index('idx_status', 'Workgroup_Schema', ['Status'], unique=False)

    op.create_table(
        'Bugs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Enum('P0', 'P1', 'P2', 'P3', 'P4'), nullable=True),
        sa.Column('bug_code', sa.String(length=50), nullable=False),
        sa.Column('bug_type', sa.Enum('repro', 'test'), nullable=False),
        sa.Column('engineer_id', sa.Integer(), nullable=True),
        sa.Column('summary', sa.String(length=255), nullable=True),
        sa.Column('station_config', sa.String(length=100), nullable=True),
        sa.Column('resource_group', sa.String(length=100), nullable=True),
        sa.Column('status', sa.Enum('pending', 'running', 'scheduled', 'completed'), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['engineer_id'], ['Users.ID'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bug_code')
    )
    op.create_index('idx_bug_code', 'Bugs', ['bug_code'], unique=False)
    op.create_index('idx_engineer', 'Bugs', ['engineer_id'], unique=False)
    op.create_index('idx_priority', 'Bugs', ['priority'], unique=False)
    op.create_index('idx_status', 'Bugs', ['status'], unique=False)
    op.create_index('idx_bug_type', 'Bugs', ['bug_type'], unique=False)

    op.create_table(
        'Bug_Tests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bug_id', sa.Integer(), nullable=True),
        sa.Column('test_name', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['bug_id'], ['Bugs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_bug', 'Bug_Tests', ['bug_id'], unique=False)

    op.create_table(
        'Bug_stations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('bug_id', sa.Integer(), nullable=True),
        sa.Column('station_name', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['bug_id'], ['Bugs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_bug', 'Bug_stations', ['bug_id'], unique=False)

    op.create_table(
        'workgroup_assignments',
        sa.Column('ID', sa.Integer(), nullable=False),
        sa.Column('Workgroup_ID', sa.Integer(), nullable=False),
        sa.Column('Employee_ID', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['Workgroup_ID'], ['Workgroup_Schema.ID'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['Employee_ID'], ['Users.ID'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('ID'),
        sa.UniqueConstraint('Workgroup_ID', 'Employee_ID', name='unique_assignment')
    )
    op.create_index('idx_workgroup', 'workgroup_assignments', ['Workgroup_ID'], unique=False)
    op.create_index('idx_employee', 'workgroup_assignments', ['Employee_ID'], unique=False)


def downgrade():
    op.drop_index('idx_employee', table_name='workgroup_assignments')
    op.drop_index('idx_workgroup', table_name='workgroup_assignments')
    op.drop_table('workgroup_assignments')

    op.drop_index('idx_bug', table_name='Bug_stations')
    op.drop_table('Bug_stations')

    op.drop_index('idx_bug', table_name='Bug_Tests')
    op.drop_table('Bug_Tests')

    op.drop_index('idx_bug_type', table_name='Bugs')
    op.drop_index('idx_status', table_name='Bugs')
    op.drop_index('idx_priority', table_name='Bugs')
    op.drop_index('idx_engineer', table_name='Bugs')
    op.drop_index('idx_bug_code', table_name='Bugs')
    op.drop_table('Bugs')

    op.drop_index('idx_status', table_name='Workgroup_Schema')
    op.drop_index('idx_manager', table_name='Workgroup_Schema')
    op.drop_table('Workgroup_Schema')

    op.drop_index('idx_email', table_name='Users')
    op.drop_index('idx_role', table_name='Users')
    op.drop_table('Users')
