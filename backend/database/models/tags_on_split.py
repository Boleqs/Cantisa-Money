import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class TagsOnSplits(Base):
    __tablename__ = 'tags_on_split'
    __table_args__ = (
        PrimaryKeyConstraint('split_id', 'tag_id'),
        ForeignKeyConstraint(['split_id'], ['splits.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
    )

    split_id:uuid = Column(UUID(as_uuid=True))
    tag_id:uuid = Column(UUID(as_uuid=True))
