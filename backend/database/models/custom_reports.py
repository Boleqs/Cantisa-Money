import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, DateTime, func, PrimaryKeyConstraint, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from dataclasses import dataclass


@dataclass
class CustomReports(Base):
    __tablename__ = 'custom_reports'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id:uuid = Column(UUID(as_uuid=True), nullable=False)
    name:str = Column(String(100), nullable=False)
    # { filters: [{field, operator, value}], group_by, metric, chart_type, start_date, end_date }
    # chart_type/start_date/end_date sont opaques côté backend (juste stockés/restitués) — seuls
    # filters/group_by/metric sont interprétés (et revalidés) au moment de /reports/custom/run.
    config = Column(JSONB, nullable=False)
    created_at:datetime = Column(DateTime, default=func.current_timestamp())
    updated_at:datetime = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
