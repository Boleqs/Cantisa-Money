import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Numeric, DateTime, func, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class TaxHouseholdIncome(Base):
    __tablename__ = 'tax_household_income'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['household_profile_id'], ['tax_household_profile.id'], ondelete='CASCADE'),
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    household_profile_id:uuid = Column(UUID(as_uuid=True), nullable=False)
    label:str = Column(String(200), nullable=False)
    amount:int = Column(Numeric, nullable=False)
    income_type:str = Column(String(32), nullable=False, default='other')
    created_at:datetime = Column(DateTime, default=func.current_timestamp())
