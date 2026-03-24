from app.extensions import db


class MLAnalysis(db.Model):

    __tablename__ = "ML_Analysis"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    bug_id = db.Column(
        db.Integer,
        db.ForeignKey("Bugs.id", ondelete="CASCADE"),
        unique=True
    )

    repro_actions = db.Column(db.Text)
    config_changes = db.Column(db.Text)
    repro_readiness = db.Column(db.Text)
    summary = db.Column(db.Text)

    generated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.func.current_timestamp()
    )

    # Index
    __table_args__ = (
        db.Index('idx_ml_analysis_bug', 'bug_id'),
    )

    bug = db.relationship(
        "Bug",
        back_populates="ml_analysis"
    )
