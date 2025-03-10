import uuid
from .base import Base
from sqlalchemy import Column, String, DateTime, func, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID

#TODO make username unique
class Users(Base):
    __tablename__ = 'users'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
    )

    id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    username = Column(String(50), index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())



