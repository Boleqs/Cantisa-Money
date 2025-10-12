import uuid
from .base import Base
from sqlalchemy import Column, String, DateTime, func, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID


class Permissions(Base):
    __tablename__ = 'permissions'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
    )

    id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(String(250))

