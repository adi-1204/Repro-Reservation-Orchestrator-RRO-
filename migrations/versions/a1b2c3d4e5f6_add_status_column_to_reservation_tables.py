"""add status column to reservation tables

Revision ID: a1b2c3d4e5f6
Revises: k2l3m4n5o6p7
Create Date: 2026-04-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'k2l3m4n5o6p7'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    
    # Add status column to Reservations_By_Name
    by_name_columns = {col['name'] for col in inspector.get_columns('Reservations_By_Name')}
    if 'status' not in by_name_columns:
        op.add_column('Reservations_By_Name', 
            sa.Column('status', sa.Enum('pending', 'completed', 'rejected'), nullable=False, server_default='pending')
        )
    
    # Add status column to Reservations_By_Config
    by_config_columns = {col['name'] for col in inspector.get_columns('Reservations_By_Config')}
    if 'status' not in by_config_columns:
        op.add_column('Reservations_By_Config', 
            sa.Column('status', sa.Enum('pending', 'completed', 'rejected'), nullable=False, server_default='pending')
        )


def downgrade():
    op.drop_column('Reservations_By_Config', 'status')
    op.drop_column('Reservations_By_Name', 'status')
