import uuid
from .base import Base
from datetime import datetime, timedelta
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKeyConstraint, UniqueConstraint, \
    PrimaryKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID


class Budgets(Base):
    __tablename__ = 'budgets'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),

    )
    user_id = Column(UUID(as_uuid=True))
    id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    amount_allocated = Column(Numeric, nullable=False)
    amount_spent = Column(Numeric, default=0, nullable=False)
    start_date = Column(DateTime, default=datetime.now(), nullable=False)
    end_date = Column(DateTime, default=datetime.now() + timedelta(days=365), nullable=False)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())

