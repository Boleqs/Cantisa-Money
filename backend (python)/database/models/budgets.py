import uuid
from ..database import db
from datetime import datetime


class Budgets(db.Model):
    __tablename__ = 'budgets'
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), primary_key=True)
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    amount_allocated = db.Column(db.Integer, nullable=False)
    amount_spent = db.Column(db.Integer, default=0, nullable=False)
    start_date = db.Column(db.Date, default=datetime.now(), nullable=False)
    end_date = db.Column(db.Date, default=datetime.now(), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now())
    updated_at = db.Column(db.DateTime, default=datetime.now(), onupdate=datetime.now())
