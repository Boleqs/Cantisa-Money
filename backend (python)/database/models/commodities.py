import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID


class Commodities(Base):
    __tablename__ = 'commodities'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),

        UniqueConstraint('user_id', 'short_name'),
        UniqueConstraint('id'),
        CheckConstraint("type in ('Currency', 'Crypto')")

    )
    user_id = Column(UUID(as_uuid=True))
    id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name = Column(String(128), nullable=False)
    short_name = Column(String(6), nullable=False)
    type = Column(String(8), nullable=False, default='Currency')
    fraction = Column(SmallInteger, default=2, nullable=False)
    description = Column(String(1024))
    created_at = Column(DateTime, default=func.current_timestamp())


