import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, LargeBinary, Integer, CheckConstraint, \
    ForeignKeyConstraint, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class FinancialDocuments(Base):
    """Coffre-fort de documents financiers (RIB, contrats d'assurance, avis d'imposition, actes de
    propriété...) — distinct de TransactionDocuments (justificatifs toujours rattachés à une
    transaction) et de FiscaliteDossier (récapitulatif calculé, pas un espace de stockage).
    Rattachement à un compte/actif/prêt volontairement optionnel (voir CheckConstraint num_nonnulls)
    : la plupart des documents (ex. avis d'imposition) ne concernent aucune entité précise."""
    __tablename__ = 'financial_documents'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['linked_account_id'], ['accounts.id'], ondelete='SET NULL', onupdate='CASCADE'),
        ForeignKeyConstraint(['linked_asset_id'], ['assets.id'], ondelete='SET NULL'),
        ForeignKeyConstraint(['linked_loan_id'], ['loans.id'], ondelete='SET NULL'),
        CheckConstraint(
            "num_nonnulls(linked_account_id, linked_asset_id, linked_loan_id) <= 1",
            name='ck_financial_documents_single_link'),
    )

    id: uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id: uuid = Column(UUID(as_uuid=True), nullable=False)
    original_filename: str = Column(String(256), nullable=False)
    mime_type: str = Column(String(100), nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    # Taille en octets, dénormalisée depuis file_data — évite de rapatrier le blob complet côté
    # Python juste pour afficher une taille dans la liste (voir rt_financial_documents.py).
    file_size: int = Column(Integer, nullable=False, server_default='0')
    category: str = Column(String(30), nullable=False)
    description: str = Column(Text, nullable=True)
    # Texte OCR (voir utils/receipt_ocr.py::extract_text), NULL si l'OCR a échoué ou n'a rien
    # trouvé — un échec d'OCR ne doit jamais empêcher l'enregistrement du document lui-même, la
    # recherche dans le contenu n'est qu'un bonus. Sert uniquement à la recherche (ILIKE), jamais
    # affiché tel quel.
    extracted_text: str = Column(Text, nullable=True)
    linked_account_id: uuid = Column(UUID(as_uuid=True), nullable=True)
    linked_asset_id: uuid = Column(UUID(as_uuid=True), nullable=True)
    linked_loan_id: uuid = Column(UUID(as_uuid=True), nullable=True)
    uploaded_at: datetime = Column(DateTime, nullable=False, default=datetime.now)
