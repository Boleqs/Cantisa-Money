import uuid
from ..database import db
from datetime import datetime


class Assets(db.Model):
    __tablename__ = 'assets'

    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), primary_key=True)
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    symbol = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    asset_type = db.Column(db.String(20), nullable=False)
    sector = db.Column(db.String(50), nullable=True)
    commodity = db.Column(db.String(6), db.ForeignKey('commodities.short_name'), nullable=False)
    value_per_unit = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(), nullable=False)

