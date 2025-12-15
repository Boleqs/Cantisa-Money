import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class Subscriptions(Base):
    __tablename__ = 'subscriptions'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'],['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['from_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        ForeignKeyConstraint(['to_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL', onupdate='CASCADE'),

        UniqueConstraint('user_id', 'name')
    )

    user_id:uuid = Column(UUID(as_uuid=True))
    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name:str = Column(String(64), nullable=False)
    recurrence:int = Column(SmallInteger, nullable=False, default=30)
    amount:int = Column(Numeric, nullable=False, default=0)
    from_account_id:uuid = Column(UUID(as_uuid=True))
    to_account_id: uuid = Column(UUID(as_uuid=True))
    category_id:uuid = Column(UUID(as_uuid=True))
    created_at:datetime = Column(DateTime, default=func.current_timestamp())
    updated_at: datetime = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
