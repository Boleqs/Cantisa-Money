import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID


class BudgetCategories(Base):
    __tablename__ = 'budget_categories'
    __table_args__ = (
        PrimaryKeyConstraint('budget_id', 'category_id'),
        ForeignKeyConstraint(['budget_id'], ['budgets.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
    )

    budget_id = Column(UUID(as_uuid=True))
    category_id = Column(UUID(as_uuid=True))
