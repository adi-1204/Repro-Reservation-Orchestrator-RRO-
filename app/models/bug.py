from app.extensions import db

class Bug(db.Model):

    __tablename__ = "Bugs"

    bug_id = db.Column(db.String(100), primary_key=True)
    bug_name = db.Column(db.String(255))

    bug_type = db.Column(
        db.Enum('repro', 'test'),
        nullable=False,
        default='repro',
        server_default='repro'
    )

    priority = db.Column(db.String(10), default='P2')

    status = db.Column(
        db.Enum('pending', 'running', 'completed'),
        nullable=False,
        default='pending',
        server_default='pending'
    )

    build_id = db.Column(db.String(100), db.ForeignKey("Builds.version", ondelete="CASCADE"), nullable=False)

    # Bug metadata from Bugzilla
    product = db.Column(db.String(100))
    component = db.Column(db.String(100))
    reporter = db.Column(db.String(100))
    
    severity = db.Column(
        db.Enum('trivial', 'normal', 'major', 'critical', 'enhancement'),
        default='normal'
    )
    
    whiteboard = db.Column(db.Text)
    developer_progress = db.Column(db.String(255))

    engineer_id = db.Column(
        db.Integer,
        db.ForeignKey("Users.ID", ondelete="SET NULL")
    )
    
    assignee_email = db.Column(db.String(100))

    workgroup_id = db.Column(
        db.Integer,
        db.ForeignKey("Workgroup_Schema.ID", ondelete="CASCADE")
    )

    # Indexes
    __table_args__ = (
        db.Index('idx_bug_status', 'status'),
        db.Index('idx_bug_type', 'bug_type'),
        db.Index('idx_bug_workgroup', 'workgroup_id'),
    )

    engineer = db.relationship(
        "User",
        back_populates="bugs"
    )

    workgroup = db.relationship(
        "Workgroup",
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

    run_parameters = db.relationship(
        "RunParameter",
        back_populates="bug",
        cascade="all, delete-orphan"
    )

    build_record = db.relationship(
        "Build",
        back_populates="bugs",
        foreign_keys=[build_id]
    )