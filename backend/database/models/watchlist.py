import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class Watchlist(Base):
    __tablename__ = 'watchlist'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        UniqueConstraint('user_id', 'ticker'),
    )

    id:      uuid     = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id: uuid     = Column(UUID(as_uuid=True), nullable=False)
    ticker:  str      = Column(String(20), nullable=False)
    added_at: datetime = Column(DateTime, nullable=False, default=datetime.now)
