import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID


class Subscriptions(Base):
    __tablename__ = 'subscriptions'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'],['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE', onupdate='CASCADE'),
        ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE', onupdate='CASCADE'),

        UniqueConstraint('user_id', 'name')
    )

    user_id = Column(UUID(as_uuid=True))
    id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name = Column(String(64), nullable=False)
    recurrence = Column(SmallInteger, nullable=False, default=30)
    amount = Column(Numeric, nullable=False, default=0)
    account_id = Column(UUID(as_uuid=True))
    category_id = Column(UUID(as_uuid=True))
    created_at = Column(DateTime, default=func.current_timestamp())
