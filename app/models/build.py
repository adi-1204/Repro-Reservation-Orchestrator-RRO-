from app.extensions import db

class Build(db.Model):
    __tablename__ = "Builds"

    version = db.Column(db.String(100), primary_key=True)

    # Relationships
    bugs = db.relationship(
        "Bug",
        back_populates="build_record",
        cascade="all, delete-orphan",
        primaryjoin="Build.version == Bug.build_id",
        foreign_keys="Bug.build_id"
    )

    def __init__(self, version):
        self.version = version

    def __repr__(self):
        return f"<Build {self.version}>"
