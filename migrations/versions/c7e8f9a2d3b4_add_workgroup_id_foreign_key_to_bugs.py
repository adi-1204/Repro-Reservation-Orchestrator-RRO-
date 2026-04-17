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
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {col['name'] for col in inspector.get_columns('Bugs')}
    existing_fks = {fk.get('name') for fk in inspector.get_foreign_keys('Bugs')}
    existing_indexes = {idx.get('name') for idx in inspector.get_indexes('Bugs')}

    with op.batch_alter_table('Bugs', schema=None) as batch_op:
        if 'workgroup_id' not in existing_columns:
            batch_op.add_column(sa.Column('workgroup_id', sa.Integer(), nullable=True))

        if 'fk_bugs_workgroup_id' not in existing_fks:
            batch_op.create_foreign_key(
                'fk_bugs_workgroup_id',
                'Workgroup_Schema',
                ['workgroup_id'],
                ['ID'],
                ondelete='SET NULL'
            )

        if 'idx_bug_workgroup' not in existing_indexes:
            batch_op.create_index('idx_bug_workgroup', ['workgroup_id'], unique=False)


def downgrade():
    # Remove workgroup_id column from Bugs table
    with op.batch_alter_table('Bugs', schema=None) as batch_op:
        batch_op.drop_index('idx_bug_workgroup')
        batch_op.drop_constraint('fk_bugs_workgroup_id', type_='foreignkey')
        batch_op.drop_column('workgroup_id')
