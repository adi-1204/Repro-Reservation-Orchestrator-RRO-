"""add product component reporter severity whiteboard developer_progress to bugs

Revision ID: g0c9d8e7f6a5
Revises: f9b8c7d6e5a4
Create Date: 2026-04-15 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g0c9d8e7f6a5'
down_revision = 'f9b8c7d6e5a4'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add missing bug metadata columns to Bugs table:
    - product: Product name (e.g., Remote Copy, Volume Manager)
    - component: Component name (e.g., FC, IP, General)
    - reporter: Reporter email (supports external emails)
    - severity: Bug severity level
    - whiteboard: Whiteboard notes and flags
    - developer_progress: Current development status
    
    These columns are populated from Bugzilla bug data and used for
    filtering, categorization, and tracking bug metadata in dashboards.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    bugs_columns = {col['name'] for col in inspector.get_columns('Bugs')}
    
    # Add new columns if they don't exist
    if 'product' not in bugs_columns:
        op.add_column('Bugs', sa.Column('product', sa.String(length=100), nullable=True))
    
    if 'component' not in bugs_columns:
        op.add_column('Bugs', sa.Column('component', sa.String(length=100), nullable=True))
    
    if 'reporter' not in bugs_columns:
        op.add_column('Bugs', sa.Column('reporter', sa.String(length=100), nullable=True))
    
    if 'severity' not in bugs_columns:
        op.add_column('Bugs', sa.Column('severity', 
            sa.Enum('trivial', 'normal', 'major', 'critical', 'enhancement', 
                    name='bug_severity'),
            nullable=True))
    
    if 'whiteboard' not in bugs_columns:
        op.add_column('Bugs', sa.Column('whiteboard', sa.Text(), nullable=True))
    
    if 'developer_progress' not in bugs_columns:
        op.add_column('Bugs', sa.Column('developer_progress', sa.String(length=255), nullable=True))


def downgrade():
    """Remove the added columns."""
    op.drop_column('Bugs', 'developer_progress')
    op.drop_column('Bugs', 'whiteboard')
    op.drop_column('Bugs', 'severity')
    op.drop_column('Bugs', 'reporter')
    op.drop_column('Bugs', 'component')
    op.drop_column('Bugs', 'product')
