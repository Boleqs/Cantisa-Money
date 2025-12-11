import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class BudgetAccounts(Base):
    __tablename__ = 'budget_accounts'
    __table_args__ = (
        PrimaryKeyConstraint('budget_id', 'account_id'),
        ForeignKeyConstraint(['budget_id'], ['budgets.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    )

    budget_id:uuid = Column(UUID(as_uuid=True))
    account_id:uuid = Column(UUID(as_uuid=True))
