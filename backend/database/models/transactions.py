import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKeyConstraint, UniqueConstraint, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID


class Transactions(Base):
    __tablename__ = 'transactions'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'],['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['currency_id'],['commodities.id'], ondelete='CASCADE', onupdate='CASCADE'),

        UniqueConstraint('id')
    )

    user_id = Column(UUID(as_uuid=True))
    id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    currency_id = Column(UUID(as_uuid=True))
    post_date = Column(DateTime, nullable=False, default=datetime.now())
    effective_date = Column(DateTime, nullable=False, default=datetime.now())
    description = Column(String(1024), nullable=True)
    category_id = Column(UUID(as_uuid=True), default='N/A')


