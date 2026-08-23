import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, DateTime, PrimaryKeyConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from dataclasses import dataclass


@dataclass
class ReceiptTemplates(Base):
    __tablename__ = 'receipt_templates'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),

        # Un seul gabarit actif par marchand et par utilisateur — le réenregistrer sur le même
        # marchand écrase l'ancien plutôt que d'en empiler un second (voir rt_receipt_templates.py).
        UniqueConstraint('user_id', 'merchant_key'),
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id:uuid = Column(UUID(as_uuid=True))
    merchant_name:str = Column(String(100), nullable=False)
    # Nom marchand normalisé (majuscules, sans accents/espaces superflus) — clé de correspondance
    # exacte avec le marchand détecté par l'OCR généraliste sur un nouveau ticket, même logique que
    # ImportCategoryRules.keyword.
    merchant_key:str = Column(String(100), nullable=False)
    # [{'label': 'marchand'|'date'|'total'|'articles', 'top': float, 'left': float, 'width': float,
    # 'height': float}] — coordonnées en pourcentage de l'image (0-100), pas en pixels : tolère les
    # légères différences de cadrage d'une photo à l'autre du même ticket. Voir
    # backend/utils/receipt_ocr.py::apply_template.
    zones:list = Column(JSONB, nullable=False)
    created_at:datetime = Column(DateTime, nullable=False, default=datetime.now())
    updated_at:datetime = Column(DateTime, nullable=False, default=datetime.now())
