import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric


class BudgetTags(Base):
    __tablename__ = 'budget_tags'
    __table_args__ = (
        PrimaryKeyConstraint('budget_id', 'tag_id'),
        ForeignKeyConstraint(['budget_id'], ['budgets.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
    )

    budget_id = Column(String(36), nullable=False)
    tag_id = Column(String(36), nullable=False)
