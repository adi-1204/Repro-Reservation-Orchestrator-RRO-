"""add station_name to run parameters

Revision ID: k2l3m4n5o6p7
Revises: j1f2g3h4i5j6
Create Date: 2026-04-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'k2l3m4n5o6p7'
down_revision = 'j1f2g3h4i5j6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()
    table_names_lc = {name.lower(): name for name in table_names}
    run_params_table_name = table_names_lc.get('run_parameters')

    if run_params_table_name is None:
        return

    existing_columns = {col['name'].lower() for col in inspector.get_columns(run_params_table_name)}
    if 'station_name' not in existing_columns:
        op.add_column(run_params_table_name, sa.Column('station_name', sa.String(length=500), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()
    table_names_lc = {name.lower(): name for name in table_names}
    run_params_table_name = table_names_lc.get('run_parameters')

    if run_params_table_name is None:
        return

    existing_columns = {col['name'].lower() for col in inspector.get_columns(run_params_table_name)}
    if 'station_name' in existing_columns:
        op.drop_column(run_params_table_name, 'station_name')
