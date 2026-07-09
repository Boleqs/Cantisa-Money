import uuid
from .base import Base
from datetime import datetime, date
from sqlalchemy import Column, Date, DateTime, Numeric, PrimaryKeyConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class WealthSnapshot(Base):
    __tablename__ = 'wealth_snapshot'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        UniqueConstraint('user_id', 'snapshot_date'),
    )

    id:uuid              = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id:uuid          = Column(UUID(as_uuid=True), nullable=False)
    snapshot_date:date    = Column(Date, nullable=False)
    bank_net_worth:int    = Column(Numeric, nullable=False)
    portfolio_value:int   = Column(Numeric, nullable=False)
    total:int             = Column(Numeric, nullable=False)
    created_at:datetime   = Column(DateTime, default=datetime.now, nullable=False)
