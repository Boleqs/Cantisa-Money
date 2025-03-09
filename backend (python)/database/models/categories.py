import uuid
from sqlalchemy import UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func


class Categories(Base):
    __tablename__ = 'categories'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'],['users.id'], ondelete='CASCADE'),

        UniqueConstraint('user_id', 'name'),
        UniqueConstraint('id'),
        UniqueConstraint('name')
    )

    id = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now())
