import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, PrimaryKeyConstraint, \
    ForeignKeyConstraint, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class Institutions(Base):
    __tablename__ = 'institutions'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),

        UniqueConstraint('user_id', 'name'),
        UniqueConstraint('id'),

        CheckConstraint("color IN ('green', 'red', 'blue', 'white', 'black', 'yellow', 'purple')"),
        CheckConstraint("sync_status IN ('not_connected', 'connected', 'error', 'syncing')"),
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id:uuid = Column(UUID(as_uuid=True))
    name:str = Column(String(128), nullable=False)
    bic:str = Column(String(32), nullable=True)
    website:str = Column(String(256), nullable=True)
    notes:str = Column(String(1024), nullable=True)
    color:str = Column(String(16), nullable=False, default='blue')
    # Placeholders génériques pour une future connectivité de synchro bancaire (Powens,
    # GoCardless...) : aucun provider n'est branché aujourd'hui, ces colonnes ne portent que
    # du statut/identifiant, jamais de secret (tokens/credentials -> sujet à part, chiffré).
    sync_provider:str = Column(String(64), nullable=True)
    external_institution_id:str = Column(String(128), nullable=True)
    connection_id:str = Column(String(128), nullable=True)
    sync_status:str = Column(String(32), nullable=False, default='not_connected')
    sync_enabled:bool = Column(Boolean, nullable=False, default=False)
    last_synced_at:datetime = Column(DateTime, nullable=True)
    created_at:datetime = Column(DateTime, nullable=False, default=datetime.now())
