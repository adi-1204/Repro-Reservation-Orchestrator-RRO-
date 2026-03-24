from app.extensions import db


class BugStation(db.Model):

    __tablename__ = "Bug_stations"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    bug_id = db.Column(
        db.Integer,
        db.ForeignKey("Bugs.id", ondelete="CASCADE")
    )

    station_name = db.Column(db.String(100))

    # Index
    __table_args__ = (
        db.Index('idx_bug_station_bug', 'bug_id'),
    )

    bug = db.relationship(
        "Bug",
        back_populates="stations"
    )