import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, DateTime, PrimaryKeyConstraint, ForeignKeyConstraint, \
    UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class BankConnections(Base):
    __tablename__ = 'bank_connections'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['institution_id'], ['institutions.id'], ondelete='SET NULL', onupdate='CASCADE'),
        ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='SET NULL', onupdate='CASCADE'),

        UniqueConstraint('id'),
        UniqueConstraint('state'),

        CheckConstraint("status IN ('pending', 'needs_linking', 'connected', 'error', 'expired')"),
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id:uuid = Column(UUID(as_uuid=True))
    institution_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    account_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    sync_provider:str = Column(String(64), nullable=False)
    aspsp_name:str = Column(String(256), nullable=False)
    aspsp_country:str = Column(String(8), nullable=False)
    # CSRF de la demande d'autorisation en cours ; remis à None une fois échangé contre une session.
    state:uuid = Column(UUID(as_uuid=True), nullable=True)
    session_id:str = Column(String(256), nullable=True)
    external_account_uid:str = Column(String(256), nullable=True)
    # Nom/devise du compte tels que renvoyés par la banque — sert uniquement à aider l'utilisateur
    # à distinguer plusieurs comptes lors de la liaison (status 'needs_linking'), pas de valeur
    # métier après coup.
    external_account_name:str = Column(String(256), nullable=True)
    external_account_currency:str = Column(String(8), nullable=True)
    status:str = Column(String(32), nullable=False, default='pending')
    valid_until:datetime = Column(DateTime, nullable=True)
    last_synced_at:datetime = Column(DateTime, nullable=True)
    created_at:datetime = Column(DateTime, nullable=False, default=datetime.now())
