from datetime import datetime
from app.extensions import db

class ReservationByName(db.Model):
    __tablename__ = 'Reservations_By_Name'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.ID'), nullable=False)
    bug_id = db.Column(db.String(100), db.ForeignKey('Bugs.bug_id', ondelete="CASCADE"), nullable=False) # type: ignore
    stations = db.Column(db.String(500), nullable=False)  # Comma-separated station names
    specify_station = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('reservations_by_name', lazy=True))

    def __repr__(self):
        return f'<ReservationByName {self.bug_id} by User {self.user_id}>'
