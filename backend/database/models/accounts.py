import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, Boolean, Numeric, PrimaryKeyConstraint, \
    ForeignKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class Accounts(Base):
    __tablename__ = 'accounts'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['currency_id'], ['commodities.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['parent_id'],['accounts.id'], ondelete='SET NULL', onupdate='CASCADE'),
        # SET NULL (pas CASCADE) : supprimer une institution ne doit jamais supprimer les
        # comptes qu'elle contenait, même logique que parent_id ci-dessus.
        ForeignKeyConstraint(['institution_id'],['institutions.id'], ondelete='SET NULL', onupdate='CASCADE'),

        # Unicité du nom scopée, pas globale par utilisateur : deux comptes peuvent porter le même
        # nom (ex. "Compte Courant" dans deux banques différentes, ou un compte de dépense "EDF"
        # sous deux parents différents) tant qu'ils ne partagent ni le même compte parent ni la
        # même institution. Un compte sans parent ET sans institution n'est protégé par aucune des
        # deux (comportement voulu : rien à quoi le scoper).
        UniqueConstraint('user_id', 'parent_id', 'name', name='uq_accounts_user_parent_name'),
        UniqueConstraint('user_id', 'institution_id', 'name', name='uq_accounts_user_institution_name'),
        UniqueConstraint('id'),

        CheckConstraint("account_type IN ('Income', 'Expense', 'Equity', 'Assets', 'Current', 'Liability')"),
        # 'loan' : compte d'ouverture auto-généré pour un crédit déjà en cours (voir rt_loans.py,
        # jamais sélectionnable manuellement dans AccountModal.vue).
        CheckConstraint("(account_type = 'Equity' AND account_subtype IN ('fr_PEA', 'Other', 'loan')) "
                        "OR account_subtype is NULL")
    )

    user_id:uuid = Column(UUID(as_uuid=True))
    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name:str = Column(String(128), nullable=False)
    parent_id:uuid = Column(UUID(as_uuid=True))
    institution_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    account_type:str = Column(String(64), nullable=False, default='Current')
    account_subtype:str = Column(String(64), nullable=True)
    currency_id:uuid = Column(UUID(as_uuid=True), nullable=False)
    description:str = Column(String(1024), nullable=True)
    total_spent:int = Column(Numeric, default=0, nullable=False)
    total_earned:int = Column(Numeric, default=0, nullable=False)
    # Solde consolidé = total propre + somme récursive des enfants (maintenu par
    # trigger, voir propagate_consolidated_totals() dans les migrations Alembic).
    consolidated_spent:int = Column(Numeric, default=0, nullable=False)
    consolidated_earned:int = Column(Numeric, default=0, nullable=False)
    is_virtual:bool = Column(Boolean, default=False, nullable=False)
    is_hidden:bool = Column(Boolean, default=False, nullable=False)
    is_closed:bool = Column(Boolean, default=False, nullable=False)
    closed_at:datetime = Column(DateTime, nullable=True)
    code:str = Column(String(64), nullable=True)
    # 'taxable_income' | 'deductible' | 'real_estate_income' | 'real_estate_expense' | None (non fiscal)
    tax_treatment:str = Column(String(32), nullable=True)
    created_at:datetime = Column(DateTime, default=datetime.now())
    updated_at:datetime = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
