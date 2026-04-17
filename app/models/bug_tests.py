from app.extensions import db


class BugTest(db.Model):

    __tablename__ = "Bug_Tests"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    bug_id = db.Column(
        db.String(100),
        db.ForeignKey("Bugs.bug_id", ondelete="CASCADE"),
        nullable=False
    )

    test_name = db.Column(db.String(200), nullable=False)
    station_name = db.Column(db.String(100))
    build_id = db.Column(db.String(100))
    configuration = db.Column(db.String(100))

    # Indexes
    __table_args__ = (
        db.Index('idx_bug_tests_bug', 'bug_id'),
    )

    bug = db.relationship(
        "Bug",
        back_populates="tests"
    )