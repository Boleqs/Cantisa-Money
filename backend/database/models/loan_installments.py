import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, Integer, Date, DateTime, func, Boolean, Numeric, \
    PrimaryKeyConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class LoanInstallments(Base):
    __tablename__ = 'loan_installments'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['loan_id'], ['loans.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ondelete='SET NULL'),
        ForeignKeyConstraint(['rate_revision_id'], ['loan_rate_revisions.id'], ondelete='SET NULL'),

        UniqueConstraint('loan_id', 'installment_number'),
    )

    id: uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    loan_id: uuid = Column(UUID(as_uuid=True))
    installment_number: int = Column(Integer, nullable=False)
    due_date: datetime = Column(Date, nullable=False)
    principal_portion: int = Column(Numeric, nullable=False)
    interest_portion: int = Column(Numeric, nullable=False)
    insurance_portion: int = Column(Numeric, default=0, nullable=False)
    total_amount: int = Column(Numeric, nullable=False)
    # Solde théorique attendu après cette échéance, calculé à la génération de l'échéancier —
    # coïncide avec le solde réel du compte Liability tant que les échéances sont exécutées à
    # date, mais reste une valeur planifiée (pas relue depuis le compte).
    remaining_principal_after: int = Column(Numeric, nullable=False)
    is_paid: bool = Column(Boolean, default=False, nullable=False)
    paid_at: datetime = Column(DateTime, nullable=True)
    transaction_id: uuid = Column(UUID(as_uuid=True), nullable=True)
    rate_revision_id: uuid = Column(UUID(as_uuid=True), nullable=True)
    created_at: datetime = Column(DateTime, default=func.current_timestamp())
