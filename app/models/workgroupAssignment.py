from app.extensions import db

class WorkgroupAssignment(db.Model):

    __tablename__ = "workgroup_assignments"

    id = db.Column("ID", db.Integer, primary_key=True, autoincrement=True)

    workgroup_id = db.Column(
        "Workgroup_ID",
        db.Integer,
        db.ForeignKey("Workgroup_Schema.ID", ondelete="CASCADE"),
        nullable=False
    )

    employee_id = db.Column(
        "Employee_ID",
        db.Integer,
        db.ForeignKey("Users.ID", ondelete="CASCADE"),
        nullable=False
    )

    # Unique constraint to prevent duplicate assignments
    __table_args__ = (
        db.UniqueConstraint('Workgroup_ID', 'Employee_ID', name='unique_assignment'),
        db.Index('idx_workgroup', 'Workgroup_ID'),
        db.Index('idx_employee', 'Employee_ID'),
    )

    workgroup = db.relationship(
        "Workgroup",
        back_populates="engineers"
    )

    employee = db.relationship(
        "User",
        back_populates="assignments"
    )