import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID


class AssetPossession(Base):
    __tablename__ = 'asset_possession'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE', onupdate='CASCADE'),

        CheckConstraint("quantity <= 1000000000 AND quantity >= 0")
    )

    user_id = Column(UUID(as_uuid=True))
    id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    asset_id = Column(UUID(as_uuid=True))
    account_id = Column(UUID(as_uuid=True))
    quantity = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=func.current_timestamp())