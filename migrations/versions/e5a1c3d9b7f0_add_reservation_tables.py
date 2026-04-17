"""add reservation tables

Revision ID: e5a1c3d9b7f0
Revises: d4b7c8e1f2a3
Create Date: 2026-04-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5a1c3d9b7f0'
down_revision = 'd4b7c8e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()
    table_names_lc = {name.lower(): name for name in table_names}

    by_name_table = table_names_lc.get('reservations_by_name')
    if by_name_table is None:
        op.create_table(
            'Reservations_By_Name',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('bug_id', sa.String(length=100), nullable=False),
            sa.Column('stations', sa.String(length=500), nullable=False),
            sa.Column('specify_station', sa.Boolean(), server_default=sa.text('0'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['Users.ID'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        by_name_table = 'Reservations_By_Name'

    by_name_indexes = {idx['name'] for idx in inspector.get_indexes(by_name_table)}
    if 'idx_user_res_name' not in by_name_indexes:
        op.create_index('idx_user_res_name', 'Reservations_By_Name', ['user_id'], unique=False)

    by_config_table = table_names_lc.get('reservations_by_config')
    if by_config_table is None:
        op.create_table(
            'Reservations_By_Config',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('resource_group', sa.String(length=100), nullable=False),
            sa.Column('number_of_nodes', sa.Integer(), nullable=False),
            sa.Column('code_floor', sa.String(length=100), nullable=True),
            sa.Column('number_of_pds', sa.Integer(), nullable=False),
            sa.Column('rc', sa.Boolean(), server_default=sa.text('0'), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['Users.ID'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        by_config_table = 'Reservations_By_Config'

    by_config_indexes = {idx['name'] for idx in inspector.get_indexes(by_config_table)}
    if 'idx_user_res_config' not in by_config_indexes:
        op.create_index('idx_user_res_config', 'Reservations_By_Config', ['user_id'], unique=False)


def downgrade():
    op.drop_index('idx_user_res_config', table_name='Reservations_By_Config')
    op.drop_table('Reservations_By_Config')

    op.drop_index('idx_user_res_name', table_name='Reservations_By_Name')
    op.drop_table('Reservations_By_Name')
