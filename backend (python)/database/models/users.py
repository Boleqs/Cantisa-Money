import uuid
from ..database import db
from sqlalchemy import Column, String, DateTime, func, relationship, PrimaryKeyConstraint, ForeignKeyConstraint


class Users(db):
    __tablename__ = 'users'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
    )

    id = Column(String(36), default=str(uuid.uuid4()))
    username = Column(String(50), index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())



