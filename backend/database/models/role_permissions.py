from .base import Base
from sqlalchemy import Column, String, DateTime, func, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID


class RolePermissions(Base):
    __tablename__ = 'role_permissions'
    __table_args__ = (
        PrimaryKeyConstraint('role_id', 'permission_id'),
        ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
    )

    role_id = Column(UUID(as_uuid=True))
    permission_id = Column(UUID(as_uuid=True))