from .base import Base
from sqlalchemy import Column, String, DateTime, func, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID


class UserRoles(Base):
    __tablename__ = 'user_roles'
    __table_args__ = (
        PrimaryKeyConstraint('user_id', 'role_id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
    )

    user_id = Column(UUID(as_uuid=True))
    role_id = Column(UUID(as_uuid=True))

