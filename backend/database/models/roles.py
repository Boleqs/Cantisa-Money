import uuid
from .base import Base
from sqlalchemy import Column, String, DateTime, func, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from .role_permissions import RolePermissions


class Roles(Base):
    __tablename__ = 'roles'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
    )

    id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(String(250))
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    def check_role_permission(self, permission_id):
        return bool(RolePermissions.query.filter(RolePermissions.role_id == self.id,
                                            RolePermissions.permission_id == permission_id).first())
