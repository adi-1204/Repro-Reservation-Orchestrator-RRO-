from app.extensions import db


class Bug(db.Model):

    __tablename__ = "Bugs"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    priority = db.Column(
        db.Enum('P0', 'P1', 'P2', 'P3', 'P4'),
        default='P2'
    )

    bug_code = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    bug_name = db.Column(db.String(255), nullable=True)

    bug_type = db.Column(
        db.Enum('repro', 'test'),
        nullable=False
    )

    engineer_id = db.Column(
        db.Integer,
        db.ForeignKey("Users.ID", ondelete="SET NULL")
    )

    summary = db.Column(db.String(255))

    station_config = db.Column(db.String(100))
    resource_group = db.Column(db.String(100))

    status = db.Column(
        db.Enum('pending', 'running', 'scheduled', 'completed'),
        default='pending'
    )

    created_at = db.Column(
        db.TIMESTAMP,
        server_default=db.func.current_timestamp()
    )

    # Indexes
    __table_args__ = (
        db.Index('idx_bug_code', 'bug_code'),
        db.Index('idx_engineer', 'engineer_id'),
        db.Index('idx_priority', 'priority'),
        db.Index('idx_bug_status', 'status'),
        db.Index('idx_bug_type', 'bug_type'),
    )

    engineer = db.relationship(
        "User",
        back_populates="bugs"
    )

    tests = db.relationship(
        "BugTest",
        back_populates="bug",
        cascade="all, delete-orphan"
    )

    stations = db.relationship(
        "BugStation",
        back_populates="bug",
        cascade="all, delete-orphan"
    )

    comments = db.relationship(
        "BugComment",
        back_populates="bug",
        cascade="all, delete-orphan"
    )

    ml_analysis = db.relationship(
        "MLAnalysis",
        back_populates="bug",
        uselist=False,
        cascade="all, delete-orphan"
    )