import uuid
from .base import Base
from sqlalchemy import Column, String, DateTime, func, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class Permissions(Base):
    __tablename__ = 'permissions'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name:str = Column(String(50), unique=True, index=True, nullable=False)
    description:str = Column(String(250))

