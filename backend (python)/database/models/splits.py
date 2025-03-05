import uuid
from ..database import db


class Splits(db.Model):
    __tablename__ = 'splits'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tx_id = db.Column(db.String(36), db.ForeignKey('transactions.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    account_id = db.Column(db.String(36), db.ForeignKey('accounts.id'), nullable=False)