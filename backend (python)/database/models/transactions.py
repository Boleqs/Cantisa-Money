import uuid
from ..database import db
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, relationship, ForeignKeyConstraint, UniqueConstraint, PrimaryKeyConstraint


class Transactions(db):
    __tablename__ = 'transactions'
    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'id'),
        ForeignKeyConstraint(['user_id'],['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['currency_id'],['commodities.id'], ondelete='CASCADE', onupdate='CASCADE'),

        UniqueConstraint('id')
    )

    user_id = Column(String(36))
    id = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    currency_id = Column(String(36), nullable=False)
    post_date = Column(DateTime, nullable=False, default=datetime.now())
    effective_date = Column(DateTime, nullable=False, default=datetime.now())
    description = Column(String(1024), nullable=True)
    category_id = Column(String(36), nullable=False, default='N/A')


