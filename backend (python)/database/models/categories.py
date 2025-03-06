import uuid
from sqlalchemy import UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint
from ..database import db
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, relationship


class Categories(db):
    __tablename__ = 'categories'
    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'id'),
        ForeignKeyConstraint(['user_id'],['users.id'], ondelete='CASCADE'),

        UniqueConstraint('user_id', 'name'),
        UniqueConstraint('id'),
        UniqueConstraint('name')
    )

    id = Column(String(36), nullable=False, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.now())
