"""remove redundant columns from bugs table

Revision ID: h1d0e9f8g7b6
Revises: g0c9d8e7f6a5
Create Date: 2026-04-15 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h1d0e9f8g7b6'
down_revision = 'g0c9d8e7f6a5'
branch_labels = None
depends_on = None


def upgrade():
    """
    Remove redundant columns from Bugs table:
    - station_config: Info is already stored in BugTest table for each test
    - resource_group: No longer needed - build_id is sufficient
    - summary: Duplicate info - component describes the feature area
    
    'status' is kept as raw data from Bugzilla. Backend filtering handles
    mapping Bugzilla 'OPEN' status to 'pending actions' for UI display.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    bugs_columns = {col['name'] for col in inspector.get_columns('Bugs')}
    
    # Drop columns that exist
    if 'station_config' in bugs_columns:
        op.drop_column('Bugs', 'station_config')
    
    if 'resource_group' in bugs_columns:
        op.drop_column('Bugs', 'resource_group')
    
    if 'summary' in bugs_columns:
        op.drop_column('Bugs', 'summary')


def downgrade():
    """Restore the removed columns."""
    op.add_column('Bugs', sa.Column('summary', sa.String(length=255), nullable=True))
    op.add_column('Bugs', sa.Column('resource_group', sa.String(length=100), nullable=True))
    op.add_column('Bugs', sa.Column('station_config', sa.String(length=100), nullable=True))
