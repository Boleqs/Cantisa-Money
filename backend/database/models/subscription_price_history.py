import uuid
from .base import Base
from datetime import datetime, date
from sqlalchemy import Column, Date, DateTime, Numeric, PrimaryKeyConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class SubscriptionPriceHistory(Base):
    __tablename__ = 'subscription_price_history'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
        UniqueConstraint('subscription_id', 'effective_date'),
    )

    id:uuid              = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id:uuid          = Column(UUID(as_uuid=True), nullable=False)
    subscription_id:uuid  = Column(UUID(as_uuid=True), nullable=False)
    effective_date:date   = Column(Date, nullable=False)
    amount:int            = Column(Numeric, nullable=False)
    created_at:datetime   = Column(DateTime, default=datetime.now, nullable=False)
