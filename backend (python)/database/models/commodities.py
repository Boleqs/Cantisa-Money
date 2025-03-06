import uuid
from ..database import db
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, relationship, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint


class Commodities(db):
    __tablename__ = 'commodities'
    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),

        UniqueConstraint('user_id', 'short_name'),
        CheckConstraint("type in ('Currency', 'Crypto')")
    )
    user_id = Column(String(36), nullable=False)
    id = Column(String(36), default=str(uuid.uuid4()))
    name = Column(String(128), nullable=False)
    short_name = Column(String(6), nullable=False, unique=True)
    type = Column(String(8), nullable=False, default='Currency')
    fraction = Column(SmallInteger, default=2, nullable=False)
    description = Column(String(1024))
    created_at = Column(DateTime, default=func.current_timestamp())


