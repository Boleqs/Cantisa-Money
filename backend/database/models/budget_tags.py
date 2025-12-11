import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class BudgetTags(Base):
    __tablename__ = 'budget_tags'
    __table_args__ = (
        PrimaryKeyConstraint('budget_id', 'tag_id'),
        ForeignKeyConstraint(['budget_id'], ['budgets.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
    )

    budget_id:uuid = Column(UUID(as_uuid=True))
    tag_id:uuid = Column(UUID(as_uuid=True))
