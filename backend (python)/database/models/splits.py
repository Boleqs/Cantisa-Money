import uuid
from .base import Base
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKeyConstraint, UniqueConstraint, \
    PrimaryKeyConstraint, Numeric, CheckConstraint


class Splits(Base):
    __tablename__ = 'splits'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['tx_id'],['transactions.id'], ondelete='CASCADE', onupdate='CASCADE'),
        ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE', onupdate='CASCADE')
    )

    id = Column(String(36), default=lambda: str(uuid.uuid4()))
    tx_id = Column(String(36), nullable=False)
    quantity = Column(Numeric, nullable=False)
    account_id = Column(String(36), nullable=False)
