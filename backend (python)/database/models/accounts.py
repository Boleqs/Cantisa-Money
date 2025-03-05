import uuid
from ..database import db
from datetime import datetime


class Accounts(db.Model):
    __tablename__ = 'accounts'
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), primary_key=True)
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(128), unique=True, nullable=False)
    parent_id = db.Column(db.String(36), nullable=True)
    account_type = db.Column(db.String(64), nullable=False, default='Current')
    account_subtype = db.Column(db.String(64), nullable=True)
    currency_id = db.Column(db.String(36), db.ForeignKey('commodities.id'), nullable=False)
    description = db.Column(db.String(1024), nullable=True)
    total_spent = db.Column(db.Numeric, default=0.0, nullable=False)
    total_earned = db.Column(db.Numeric, default=0.0, nullable=False)
    is_virtual = db.Column(db.Boolean, default=False, nullable=False)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.Date, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
