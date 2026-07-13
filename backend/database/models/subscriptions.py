import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class Subscriptions(Base):
    __tablename__ = 'subscriptions'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'],['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['from_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        ForeignKeyConstraint(['to_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL', onupdate='CASCADE'),

        UniqueConstraint('user_id', 'name'),
        CheckConstraint("schedule_type IN ('monthly', 'yearly', 'weekly')"),
    )

    user_id:uuid = Column(UUID(as_uuid=True))
    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name:str = Column(String(64), nullable=False)
    # 'monthly' -> day_of_month (ex: le 6 de chaque mois)
    # 'yearly'  -> day_of_month + month_of_year (ex: tous les 5 janvier)
    # 'weekly'  -> weekdays, ISO 1=lundi..7=dimanche, ex: "3,4" (mercredi et jeudi)
    schedule_type:str = Column(String(10), nullable=False, default='monthly')
    day_of_month:int = Column(SmallInteger, nullable=True)
    month_of_year:int = Column(SmallInteger, nullable=True)
    weekdays:str = Column(String(20), nullable=True)
    amount:int = Column(Numeric, nullable=False, default=0)
    from_account_id:uuid = Column(UUID(as_uuid=True))
    to_account_id: uuid = Column(UUID(as_uuid=True))
    category_id:uuid = Column(UUID(as_uuid=True))
    last_executed_at: datetime = Column(DateTime, nullable=True)
    created_at:datetime = Column(DateTime, default=func.current_timestamp())
    updated_at: datetime = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
