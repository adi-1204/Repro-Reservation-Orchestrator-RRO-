from datetime import datetime
from app.extensions import db

class ReservationByConfig(db.Model):
    __tablename__ = 'Reservations_By_Config'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('Users.ID'), nullable=False)
    resource_group = db.Column(db.String(100), nullable=False)
    number_of_nodes = db.Column(db.Integer, nullable=False)
    code_floor = db.Column(db.String(100))
    number_of_pds = db.Column(db.Integer, nullable=False)
    rc = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('reservations_by_config', lazy=True))

    def __repr__(self):
        return f'<ReservationByConfig {self.resource_group} by User {self.user_id}>'
