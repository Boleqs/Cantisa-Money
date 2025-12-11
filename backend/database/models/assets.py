import uuid

from sqlalchemy.testing.util import drop_all_tables

from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKeyConstraint, UniqueConstraint, \
    PrimaryKeyConstraint, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass

@dataclass
class Assets(Base):
    __tablename__ = 'assets'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['commodity_id'], ['commodities.id'], ondelete='CASCADE'),

        UniqueConstraint('name', 'asset_type', 'commodity_id'),
        CheckConstraint("asset_type IN ('Stock', 'ETF', 'RealEstate', 'Vehicle', 'Other')"),
        CheckConstraint("asset_type IN ('Stock', 'ETF') OR sector IS NULL")
    )

    user_id:uuid = Column(UUID(as_uuid=True))
    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    symbol:str = Column(String(20), nullable=False)
    name:str = Column(String(100), nullable=False)
    asset_type:str = Column(String(20), nullable=False)
    sector:str = Column(String(50), nullable=True)
    commodity_id:uuid = Column(UUID(as_uuid=True))
    value_per_unit:int = Column(Numeric, default=0, nullable=False)
    created_at:datetime = Column(DateTime, default=datetime.now(), nullable=False)

