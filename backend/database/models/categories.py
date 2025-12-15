import uuid
from sqlalchemy import UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


#TODO add total spent in category
@dataclass
class Categories(Base):
    __tablename__ = 'categories'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'],['users.id'], ondelete='CASCADE'),

        UniqueConstraint('user_id', 'name'),
        UniqueConstraint('id')
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id:uuid = Column(UUID(as_uuid=True))
    name:str = Column(String(100), nullable=False)
    description:str = Column(String(1000), nullable=True)
    created_at:datetime = Column(DateTime, nullable=False, default=datetime.now())
