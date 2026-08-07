import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, DateTime, PrimaryKeyConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class ImportCategoryRules(Base):
    __tablename__ = 'import_category_rules'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL', onupdate='CASCADE'),
        ForeignKeyConstraint(['opposing_account_id'], ['accounts.id'], ondelete='SET NULL', onupdate='CASCADE'),

        UniqueConstraint('user_id', 'keyword'),
        UniqueConstraint('id'),
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id:uuid = Column(UUID(as_uuid=True))
    # Description de transaction normalisée (minuscules, sans accents/chiffres/dates) — sert de clé
    # de correspondance exacte pour réappliquer automatiquement la catégorie/contrepartie choisie
    # par l'utilisateur lors d'un import précédent, sans dépendre d'une IA externe.
    keyword:str = Column(String(255), nullable=False)
    category_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    opposing_account_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    created_at:datetime = Column(DateTime, nullable=False, default=datetime.now())
    updated_at:datetime = Column(DateTime, nullable=False, default=datetime.now())
