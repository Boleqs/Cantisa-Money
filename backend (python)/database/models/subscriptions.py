import uuid
from ..database import db
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, relationship, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric


class Subscriptions(db):
    __tablename__ = 'subscriptions'
    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'id'),
        ForeignKeyConstraint(['user_id'],['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE', onupdate='CASCADE'),
        ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE', onupdate='CASCADE'),

        UniqueConstraint('user_id', 'name'),
    )

    user_id = Column(String(36), nullable=False)
    id = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    name = Column(String(64), nullable=False)
    recurrence = Column(SmallInteger, nullable=False, default=30)
    amount = Column(Numeric, nullable=False, default=0)
    account_id = Column(String(36), nullable=False)
    category_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=func.current_timestamp())