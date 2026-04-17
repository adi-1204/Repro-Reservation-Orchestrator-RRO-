from app.extensions import db


class RunParameter(db.Model):

    __tablename__ = "Run_Parameters"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    bug_id = db.Column(
        db.String(100),
        db.ForeignKey("Bugs.bug_id", ondelete="CASCADE"),
        nullable=False
    )

    run_mode = db.Column(
        db.Enum('run_tests', 'config_and_execute'),
        nullable=False
    )

    test_name = db.Column(db.String(200))
    station_name = db.Column(db.String(500))
    run_type = db.Column(
        db.Enum('quick', 'comprehensive'),
        nullable=False
    )
    workflow = db.Column(db.String(200))
    run_count = db.Column(db.Integer)
    provision_setup = db.Column(db.Text)
    do_checkout_update = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default=db.text("0")
    )

    submitted_by = db.Column(
        db.Integer,
        db.ForeignKey("Users.ID", ondelete="SET NULL")
    )

    submitted_at = db.Column(
        db.TIMESTAMP,
        server_default=db.func.current_timestamp()
    )

    status = db.Column(
        db.Enum('queued', 'running', 'completed', 'failed'),
        nullable=False,
        default='queued',
        server_default='queued'
    )

    # Indexes
    __table_args__ = (
        db.Index('idx_run_parameters_bug', 'bug_id'),
        db.Index('idx_run_parameters_submitted_by', 'submitted_by'),
    )

    bug = db.relationship(
        "Bug",
        back_populates="run_parameters"
    )

    submitted_by_user = db.relationship(
        "User",
        back_populates="submitted_run_parameters"
    )
