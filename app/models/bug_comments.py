from app.extensions import db


class BugComment(db.Model):

    __tablename__ = "Bug_Comments"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    bug_id = db.Column(
        db.Integer,
        db.ForeignKey("Bugs.id", ondelete="CASCADE")
    )

    comment_bugzilla_id = db.Column(db.Integer)
    creator = db.Column(db.String(100))
    creation_time = db.Column(db.DateTime)
    text = db.Column(db.Text)

    # Index
    __table_args__ = (
        db.Index('idx_bug_comment_bug', 'bug_id'),
    )

    bug = db.relationship(
        "Bug",
        back_populates="comments"
    )
