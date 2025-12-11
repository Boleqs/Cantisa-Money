import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKeyConstraint, UniqueConstraint, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class Transactions(Base):
    __tablename__ = 'transactions'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'],['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['currency_id'],['commodities.id'], ondelete='CASCADE', onupdate='CASCADE'),

        UniqueConstraint('id')
    )

    user_id:uuid = Column(UUID(as_uuid=True))
    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    currency_id:uuid = Column(UUID(as_uuid=True))
    post_date:datetime = Column(DateTime, nullable=False, default=datetime.now())
    effective_date:datetime = Column(DateTime, nullable=False, default=datetime.now())
    description:str = Column(String(1024), nullable=True)
    category_id:uuid = Column(UUID(as_uuid=True), default='N/A')


