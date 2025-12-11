import uuid
from .base import Base
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKeyConstraint, UniqueConstraint, \
    PrimaryKeyConstraint, Numeric, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class Splits(Base):
    __tablename__ = 'splits'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['tx_id'],['transactions.id'], ondelete='CASCADE', onupdate='CASCADE'),
        ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE', onupdate='CASCADE')
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    tx_id:uuid = Column(UUID(as_uuid=True))
    quantity:int = Column(Numeric, nullable=False)
    account_id:uuid = Column(UUID(as_uuid=True))
