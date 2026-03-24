from app.extensions import db


class BugTest(db.Model):

    __tablename__ = "Bug_Tests"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    bug_id = db.Column(
        db.Integer,
        db.ForeignKey("Bugs.id", ondelete="CASCADE")
    )

    test_name = db.Column(db.String(100))

    test_plan_name = db.Column(db.String(200))
    test_ring_name = db.Column(db.String(100))
    execution_start = db.Column(db.DateTime)
    execution_end = db.Column(db.DateTime)
    controller_types = db.Column(db.String(100))
    number_of_nodes = db.Column(db.Integer)
    failure_type = db.Column(db.String(50))
    build_version = db.Column(db.String(50))
    configuration = db.Column(db.String(50), nullable=True)
    nfs_path = db.Column(db.String(500))
    odin_link = db.Column(db.String(500))
    signature = db.Column(db.String(500))
    station_name = db.Column(db.String(100))

    # Index
    __table_args__ = (
        db.Index('idx_bug_test_bug', 'bug_id'),
    )

    bug = db.relationship(
        "Bug",
        back_populates="tests"
    )