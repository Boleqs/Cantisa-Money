import uuid
from .base import Base
from datetime import datetime, date
from sqlalchemy import Column, String, DateTime, Date, func, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class DcaPlans(Base):
    __tablename__ = 'dca_plans'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['source_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        ForeignKeyConstraint(['dest_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),

        UniqueConstraint('user_id', 'name'),
        CheckConstraint("schedule_type IN ('monthly', 'yearly', 'weekly')"),
    )

    user_id: uuid = Column(UUID(as_uuid=True))
    id: uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name: str = Column(String(64), nullable=False)
    asset_id: uuid = Column(UUID(as_uuid=True))
    source_account_id: uuid = Column(UUID(as_uuid=True))
    dest_account_id: uuid = Column(UUID(as_uuid=True))
    amount = Column(Numeric, nullable=False, default=0)
    # Même union discriminée que Subscriptions (voir recurrence.py) :
    # 'monthly' -> day_of_month, 'yearly' -> day_of_month + month_of_year, 'weekly' -> weekdays.
    schedule_type: str = Column(String(10), nullable=False, default='monthly')
    day_of_month: int = Column(SmallInteger, nullable=True)
    month_of_year: int = Column(SmallInteger, nullable=True)
    weekdays: str = Column(String(20), nullable=True)
    # Ancre de récurrence explicite (contrairement à Subscriptions, qui retombe sur created_at) :
    # un plan DCA se planifie souvent à l'avance ("commencer en septembre").
    start_date: date = Column(Date, nullable=False)
    end_date: date = Column(Date, nullable=True)
    is_forecast_only: bool = Column(Boolean, default=False, nullable=False)
    last_executed_at: datetime = Column(DateTime, nullable=True)
    created_at: datetime = Column(DateTime, default=func.current_timestamp())
    updated_at: datetime = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
