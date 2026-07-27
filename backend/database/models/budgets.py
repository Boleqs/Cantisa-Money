import uuid
from .base import Base
from datetime import datetime, timedelta
from sqlalchemy import Column, String, Integer, DateTime, Boolean, func, ForeignKeyConstraint, UniqueConstraint, \
    PrimaryKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class Budgets(Base):
    __tablename__ = 'budgets'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),

    )
    user_id:uuid = Column(UUID(as_uuid=True))
    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name:str = Column(String(100), nullable=False, default='Budget')
    amount_allocated:int = Column(Numeric, nullable=False)
    amount_spent:int = Column(Numeric, default=0, nullable=False)
    amount_spent_incomplete:bool = Column(Boolean, default=False, nullable=False)
    start_date:datetime = Column(DateTime, default=datetime.now(), nullable=False)
    end_date:datetime = Column(DateTime, default=datetime.now() + timedelta(days=365), nullable=False)
    # 'monthly' | 'quarterly' | 'yearly' | None (pas de reconduction). Voir renew_due_budgets()
    # dans scheduler.py.
    renew_period:str = Column(String(16), nullable=True)
    # Empêche de reconduire deux fois le même budget si le job tourne plusieurs fois avant que la
    # période suivante ne soit à son tour dépassée (idempotence, même logique que Loans.is_closed).
    renewed:bool = Column(Boolean, default=False, nullable=False)
    created_at:datetime = Column(DateTime, default=datetime.now())
    updated_at:datetime = Column(DateTime, default=datetime.now(), onupdate=datetime.now())

