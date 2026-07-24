import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, func, PrimaryKeyConstraint, \
    ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class TaxHouseholdProfile(Base):
    __tablename__ = 'tax_household_profile'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        UniqueConstraint('user_id', 'tax_year'),
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id:uuid = Column(UUID(as_uuid=True), nullable=False)
    tax_year:int = Column(Integer, nullable=False)
    adults:int = Column(Integer, nullable=False, default=1)
    dependents:int = Column(Integer, nullable=False, default=0)
    dependents_disabled:int = Column(Integer, nullable=False, default=0)
    parent_isole:bool = Column(Boolean, nullable=False, default=False)
    notes:str = Column(String(1000), nullable=True)
    created_at:datetime = Column(DateTime, default=func.current_timestamp())
    updated_at:datetime = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
