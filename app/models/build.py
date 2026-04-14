from app.extensions import db

class Build(db.Model):
    __tablename__ = "Builds"

    version = db.Column(db.String(100), primary_key=True)
    bug_id = db.Column(db.String(100), db.ForeignKey("Bugs.bug_code", ondelete="SET NULL"))
    
    # Relationships
    bugs = db.relationship(
        "Bug",
        back_populates="build_record",
        cascade="all, delete-orphan",
        primaryjoin="Build.version == Bug.build_id",
        foreign_keys="Bug.build_id"
    )
    
    workgroups = db.relationship(
        "Workgroup",
        back_populates="build_record",
        cascade="all, delete-orphan"
    )

    associated_bug = db.relationship(
        "Bug",
        foreign_keys=[bug_id],
        uselist=False
    )

    def __init__(self, version):
        self.version = version

    def __repr__(self):
        return f"<Build {self.version}>"
