from app.extensions import db

class User(db.Model):

    __tablename__ = "Users"

    id = db.Column("ID", db.Integer, primary_key=True, autoincrement=True)
    first_name = db.Column("First_Name", db.String(10), nullable=False)
    last_name = db.Column("Last_Name", db.String(10))
    email = db.Column("Email", db.String(100), unique=True, nullable=False)
    password = db.Column("Password", db.String(255), nullable=False)
    role = db.Column("Role", db.Enum('Engineer', 'Manager'), nullable=False)

    # Indexes
    __table_args__ = (
        db.Index('idx_role', 'Role'),
        db.Index('idx_email', 'Email'),
    )

    # Relationships
    managed_workgroups = db.relationship(
        "Workgroup",
        back_populates="manager",
        lazy=True
    )

    assignments = db.relationship(
        "WorkgroupAssignment",
        back_populates="employee",
        lazy=True
    )

    bugs = db.relationship(
        "Bug",
        back_populates="engineer",
        lazy=True
    )

    submitted_run_parameters = db.relationship(
        "RunParameter",
        back_populates="submitted_by_user",
        lazy=True
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name or ''}".strip()