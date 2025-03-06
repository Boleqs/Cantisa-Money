import uuid
from ..database import db
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, relationship

class Transactions(db.Model):
    __tablename__ = 'transactions'
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), primary_key=True)
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    currency_id = db.Column(db.String(36), db.ForeignKey('commodities.id'), nullable=False)
    post_date = db.Column(db.Date, default=datetime.now())
    effective_date = db.Column(db.Date, default=datetime.now())
    description = db.Column(db.String(1024), nullable=True)
    category_id = db.Column(db.String(36), nullable=False)
