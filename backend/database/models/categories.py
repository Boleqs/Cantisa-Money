import uuid
from sqlalchemy import UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID

#TODO add total spent in category
class Categories(Base):
    __tablename__ = 'categories'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'],['users.id'], ondelete='CASCADE'),

        UniqueConstraint('user_id', 'name'),
        UniqueConstraint('id'),
        UniqueConstraint('name')
    )

    id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    name = Column(String(100), nullable=False)
    description = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now())
