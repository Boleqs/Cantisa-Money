import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, Date, DateTime, func, Numeric, String, \
    PrimaryKeyConstraint, ForeignKeyConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class LoanRateRevisions(Base):
    __tablename__ = 'loan_rate_revisions'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['loan_id'], ['loans.id'], ondelete='CASCADE'),
        CheckConstraint("recalc_mode IN ('keep_term', 'keep_payment')"),
    )

    id: uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    loan_id: uuid = Column(UUID(as_uuid=True))
    effective_date: datetime = Column(Date, nullable=False)
    new_annual_rate: int = Column(Numeric, nullable=False)
    # 'keep_term'    : le nombre d'échéances restantes est conservé, la mensualité est recalculée.
    # 'keep_payment' : la mensualité (capital+intérêts) est conservée, le nombre d'échéances restantes est recalculé.
    recalc_mode: str = Column(String(16), nullable=False)
    created_at: datetime = Column(DateTime, default=func.current_timestamp())
