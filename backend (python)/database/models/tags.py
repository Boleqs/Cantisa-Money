import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID


class Tags(Base):
    __tablename__ = 'tags'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'],['users.id'], ondelete='CASCADE'),

        UniqueConstraint('user_id', 'name'),
        CheckConstraint("color in ('green', 'red', 'blue', 'white', 'black', 'yellow', 'purple')")
    )

    id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    name = Column(String(100), nullable=False)
    color = Column(String(64), nullable=False, default='green')
    created_at = Column(DateTime, nullable=False, default=datetime.now())