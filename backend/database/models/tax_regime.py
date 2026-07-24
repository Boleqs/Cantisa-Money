import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, func, PrimaryKeyConstraint, \
    ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from dataclasses import dataclass


@dataclass
class TaxRegime(Base):
    __tablename__ = 'tax_regime'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        UniqueConstraint('user_id', 'name'),
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id:uuid = Column(UUID(as_uuid=True), nullable=False)
    name:str = Column(String(100), nullable=False)
    country_code:str = Column(String(2), nullable=False, default='FR')
    tax_year:int = Column(Integer, nullable=False)
    # { income_tax: {brackets, decote, quotient_familial}, capital_gains: {} } — capital_gains
    # accepté mais ignoré par le moteur Phase 1, réservé à la Phase 2 (plus-values réalisées).
    config = Column(JSONB, nullable=False)
    is_active:bool = Column(Boolean, nullable=False, default=False)
    # False pour un régime auto-seedé (barème par défaut non vérifié) — passe à True dès que
    # l'utilisateur enregistre une modification via l'éditeur (voir rt_tax.py).
    is_verified:bool = Column(Boolean, nullable=False, default=False)
    created_at:datetime = Column(DateTime, default=func.current_timestamp())
    updated_at:datetime = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
