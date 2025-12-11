import uuid
import os
from datetime import datetime

from .base import Base
from sqlalchemy import Column, String, DateTime, func, PrimaryKeyConstraint, ForeignKeyConstraint, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from backend.utils.hash_password import hash_password
from backend.config import VAR_PWD_PEPPER
from .user_roles import UserRoles
from .role_permissions import RolePermissions
from dataclasses import dataclass


#TODO make username unique
@dataclass
class Users(Base):
    __tablename__ = 'users'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    username:str = Column(String(50), unique=True, index=True, nullable=False)
    email:str = Column(String(100), unique=True, index=True, nullable=False)
    # Type is not set so it cannot be jsonified : no risk of being sent to client
    password_hash = Column(LargeBinary(256), nullable=False)
    salt = Column(LargeBinary(16), nullable=False)
    created_at:datetime = Column(DateTime, default=func.current_timestamp())
    updated_at:datetime = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())

    def check_password(self, password):
        return self.password_hash == hash_password(password, self.salt, VAR_PWD_PEPPER)

    def set_password(self, new_password):
        self.salt = os.urandom(32)
        self.password_hash = hash_password(new_password, self.salt, VAR_PWD_PEPPER)

    def check_permission(self, permission_id):
        user_roles = UserRoles.query.filter(UserRoles.user_id == self.id).all()
        for role in user_roles:
            if bool(RolePermissions.query.filter(RolePermissions.role_id == role.role_id,
                                                 RolePermissions.permission_id == permission_id).first()):
                return True
        return False
