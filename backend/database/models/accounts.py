import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, Boolean, Numeric, PrimaryKeyConstraint, \
    ForeignKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID


class Accounts(Base):
    __tablename__ = 'accounts'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['currency_id'], ['commodities.id'], ondelete='CASCADE'),

        UniqueConstraint('user_id', 'name'),
        UniqueConstraint('id'),

        CheckConstraint("account_type IN ('Income', 'Expense', 'Equity', 'Assets', 'Current')"),
        CheckConstraint("(account_type = 'Equity' AND account_subtype IN ('fr_PEA', 'Other')) "
                        "OR account_subtype is NULL")
    )

    user_id = Column(UUID(as_uuid=True))
    id = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name = Column(String(128), nullable=False)
    parent_id = Column(UUID(as_uuid=True))
    account_type = Column(String(64), nullable=False, default='Current')
    account_subtype = Column(String(64), nullable=True)
    currency_id = Column(UUID(as_uuid=True))
    description = Column(String(1024), nullable=True)
    total_spent = Column(Numeric, default=0, nullable=False)
    total_earned = Column(Numeric, default=0, nullable=False)
    is_virtual = Column(Boolean, default=False, nullable=False)
    is_hidden = Column(Boolean, default=False, nullable=False)
    code = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
