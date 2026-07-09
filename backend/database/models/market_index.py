import uuid
from .base import Base
from sqlalchemy import Column, String, UniqueConstraint, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class MarketIndex(Base):
    __tablename__ = 'market_index'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        UniqueConstraint('index_name', 'ticker'),
    )

    id:         uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    index_name: str  = Column(String(64), nullable=False)
    ticker:     str  = Column(String(20), nullable=False)
