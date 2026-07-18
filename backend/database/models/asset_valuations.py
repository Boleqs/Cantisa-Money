import uuid
from .base import Base
from datetime import datetime, date
from sqlalchemy import Column, Date, DateTime, Numeric, PrimaryKeyConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class AssetValuations(Base):
    __tablename__ = 'asset_valuations'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        UniqueConstraint('asset_id', 'valuation_date'),
    )

    id:uuid               = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id:uuid           = Column(UUID(as_uuid=True), nullable=False)
    asset_id:uuid          = Column(UUID(as_uuid=True), nullable=False)
    valuation_date:date    = Column(Date, nullable=False)
    value_per_unit:int     = Column(Numeric, nullable=False)
    created_at:datetime    = Column(DateTime, default=datetime.now, nullable=False)
