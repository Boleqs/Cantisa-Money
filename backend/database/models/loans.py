import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, Date, DateTime, func, Boolean, Numeric, SmallInteger, \
    PrimaryKeyConstraint, ForeignKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class Loans(Base):
    __tablename__ = 'loans'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['payment_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        ForeignKeyConstraint(['interest_expense_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        ForeignKeyConstraint(['insurance_expense_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        ForeignKeyConstraint(['liability_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        ForeignKeyConstraint(['equity_opening_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        ForeignKeyConstraint(['opening_transaction_id'], ['transactions.id'], ondelete='SET NULL'),
        ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL', onupdate='CASCADE'),

        UniqueConstraint('user_id', 'name'),
        CheckConstraint("(is_existing_loan = false) OR (equity_opening_account_id IS NOT NULL)"),
        CheckConstraint("principal > 0"),
        CheckConstraint("annual_rate >= 0"),
        CheckConstraint("term_months >= 1"),
        CheckConstraint("payment_day BETWEEN 1 AND 31"),
    )

    user_id: uuid = Column(UUID(as_uuid=True))
    id: uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name: str = Column(String(128), nullable=False)
    # Sémantique double selon le mode (voir is_existing_loan) :
    # - nouveau crédit (is_existing_loan=False) : montant emprunté à l'origine (start_date = date de déblocage)
    # - crédit déjà en cours (is_existing_loan=True) : capital restant dû à start_date (date de saisie)
    principal: int = Column(Numeric, nullable=False)
    annual_rate: int = Column(Numeric, nullable=False)
    term_months: int = Column(Integer, nullable=False)
    start_date: datetime = Column(Date, nullable=False)
    payment_day: int = Column(SmallInteger, nullable=False)
    payment_account_id: uuid = Column(UUID(as_uuid=True), nullable=False)
    interest_expense_account_id: uuid = Column(UUID(as_uuid=True), nullable=False)
    insurance_expense_account_id: uuid = Column(UUID(as_uuid=True), nullable=True)
    insurance_monthly_amount: int = Column(Numeric, nullable=True)
    # Compte de type Liability créé automatiquement à la création du prêt (non choisi par
    # l'utilisateur) — son solde (total_earned - total_spent) est en permanence égal à
    # -(capital restant dû), voir rt_loans.py.
    liability_account_id: uuid = Column(UUID(as_uuid=True), nullable=False)
    # Requis si is_existing_loan=True : contrepartie de l'écriture d'ouverture (le compte de
    # paiement n'est pas crédité dans ce cas, les fonds ayant déjà été perçus avant l'usage de l'appli).
    equity_opening_account_id: uuid = Column(UUID(as_uuid=True), nullable=True)
    opening_transaction_id: uuid = Column(UUID(as_uuid=True), nullable=True)
    category_id: uuid = Column(UUID(as_uuid=True), nullable=True)
    # Si False (défaut) : les échéances dues ne sont jamais postées automatiquement par le
    # scheduler, juste affichées comme échéance à venir/en retard — confirmation manuelle via
    # POST /loans/execute, symétrique de Subscriptions.is_forecast_only.
    auto_debit: bool = Column(Boolean, default=False, nullable=False)
    is_existing_loan: bool = Column(Boolean, default=False, nullable=False)
    is_closed: bool = Column(Boolean, default=False, nullable=False)
    closed_at: datetime = Column(DateTime, nullable=True)
    created_at: datetime = Column(DateTime, default=func.current_timestamp())
    updated_at: datetime = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
