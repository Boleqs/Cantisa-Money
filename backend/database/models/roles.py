import uuid
from datetime import datetime

from .base import Base
from sqlalchemy import Column, String, DateTime, func, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from .role_permissions import RolePermissions
from dataclasses import dataclass


@dataclass
class Roles(Base):
    __tablename__ = 'roles'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name:str = Column(String(50), unique=True, index=True, nullable=False)
    description:str = Column(String(250))
    created_at:datetime = Column(DateTime, default=func.current_timestamp())
    updated_at:datetime = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    def check_role_permission(self, permission_id):
        return bool(RolePermissions.query.filter(RolePermissions.role_id == self.id,
                                            RolePermissions.permission_id == permission_id).first())
