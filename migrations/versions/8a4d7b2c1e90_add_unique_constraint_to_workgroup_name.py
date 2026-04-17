"""add unique constraint to workgroup name

Revision ID: 8a4d7b2c1e90
Revises: 49911e3b43cf
Create Date: 2026-03-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8a4d7b2c1e90'
down_revision = '49911e3b43cf'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_constraints = inspector.get_unique_constraints('Workgroup_Schema')
    has_constraint = any(c.get('name') == 'uq_workgroup_name' for c in unique_constraints)

    duplicate_names = bind.execute(
        sa.text(
            """
            SELECT Name
            FROM Workgroup_Schema
            WHERE Name IS NOT NULL
            GROUP BY Name
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()

    for row in duplicate_names:
        base_name = row[0]
        ids = [
            r[0] for r in bind.execute(
                sa.text(
                    """
                    SELECT ID
                    FROM Workgroup_Schema
                    WHERE Name = :name
                    ORDER BY ID ASC
                    """
                ),
                {"name": base_name}
            ).fetchall()
        ]

        for suffix, workgroup_id in enumerate(ids[1:], start=2):
            candidate = f"{base_name} ({suffix})"
            while bind.execute(
                sa.text(
                    "SELECT 1 FROM Workgroup_Schema WHERE Name = :candidate LIMIT 1"
                ),
                {"candidate": candidate}
            ).fetchone():
                suffix += 1
                candidate = f"{base_name} ({suffix})"

            bind.execute(
                sa.text(
                    "UPDATE Workgroup_Schema SET Name = :new_name WHERE ID = :workgroup_id"
                ),
                {"new_name": candidate, "workgroup_id": workgroup_id}
            )

    if not has_constraint:
        op.create_unique_constraint(
            'uq_workgroup_name',
            'Workgroup_Schema',
            ['Name']
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    unique_constraints = inspector.get_unique_constraints('Workgroup_Schema')
    has_constraint = any(c.get('name') == 'uq_workgroup_name' for c in unique_constraints)

    if has_constraint:
        op.drop_constraint(
            'uq_workgroup_name',
            'Workgroup_Schema',
            type_='unique'
        )
