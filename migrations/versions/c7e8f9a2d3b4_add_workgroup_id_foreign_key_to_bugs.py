"""add workgroup_id foreign key to bugs

Revision ID: c7e8f9a2d3b4
Revises: b510fcfa58f3
Create Date: 2026-03-26 10:48:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e8f9a2d3b4'
down_revision = 'b510fcfa58f3'
branch_labels = None
depends_on = None


def upgrade():
    # Add workgroup_id column to Bugs table
    with op.batch_alter_table('Bugs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('workgroup_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_bugs_workgroup_id', 'Workgroup_Schema', ['workgroup_id'], ['ID'], ondelete='SET NULL')
        batch_op.create_index('idx_bug_workgroup', ['workgroup_id'], unique=False)


def downgrade():
    # Remove workgroup_id column from Bugs table
    with op.batch_alter_table('Bugs', schema=None) as batch_op:
        batch_op.drop_index('idx_bug_workgroup')
        batch_op.drop_constraint('fk_bugs_workgroup_id', type_='foreignkey')
        batch_op.drop_column('workgroup_id')
