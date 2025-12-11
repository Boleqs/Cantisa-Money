import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


#TODO add symbol field for commodities (ex: € or $)
@dataclass
class Commodities(Base):
    __tablename__ = 'commodities'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),

        UniqueConstraint('user_id', 'short_name'),
        UniqueConstraint('id'),
        CheckConstraint("type in ('Currency', 'Crypto')")

    )
    user_id:uuid = Column(UUID(as_uuid=True))
    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name:str = Column(String(128), nullable=False)
    short_name:str = Column(String(6), nullable=False)
    type:str = Column(String(8), nullable=False, default='Currency')
    fraction:int = Column(SmallInteger, default=2, nullable=False)
    description:str = Column(String(1024))
    created_at:datetime = Column(DateTime, default=func.current_timestamp())


