import uuid
from ..database import db
from datetime import datetime


class Commodities(db.Model):
    __tablename__ = 'commodities'
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), primary_key=True)
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(128), nullable=False)
    short_name = db.Column(db.String(6), unique=True, nullable=True)
    type = db.Column(db.String(8), nullable=False, default='Currency')
    fraction = db.Column(db.SmallInteger, default=2, nullable=False)
    description = db.Column(db.String(1024), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now())
