import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric


class AssetPossession(Base):
    __tablename__ = 'asset_possession'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE', onupdate='CASCADE'),

        CheckConstraint("quantity <= 1000000000 AND quantity >= 0")
    )

    user_id = Column(String(36), nullable=False)
    id = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    asset_id = Column(String(36), nullable=False)
    account_id = Column(String(36), nullable=False)
    quantity = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=func.current_timestamp())