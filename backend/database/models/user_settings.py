import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, func, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from dataclasses import dataclass


@dataclass
class UserSettings(Base):
    __tablename__ = 'user_settings'
    __table_args__ = (
        PrimaryKeyConstraint('user_id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    user_id:uuid = Column(UUID(as_uuid=True))
    currency:str = Column(String(6), default='EUR', nullable=False)
    date_format:str = Column(String(16), default='fr-FR', nullable=False)
    market_score_weights = Column(JSONB, nullable=True)
    market_score_thresholds = Column(JSONB, nullable=True)
    onboarding_completed:bool = Column(Boolean, default=False, nullable=False)
    updated_at:datetime = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
