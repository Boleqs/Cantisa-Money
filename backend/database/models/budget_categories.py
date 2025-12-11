import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class BudgetCategories(Base):
    __tablename__ = 'budget_categories'
    __table_args__ = (
        PrimaryKeyConstraint('budget_id', 'category_id'),
        ForeignKeyConstraint(['budget_id'], ['budgets.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
    )

    budget_id:uuid = Column(UUID(as_uuid=True))
    category_id:uuid = Column(UUID(as_uuid=True))
