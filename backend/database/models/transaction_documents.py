import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, DateTime, LargeBinary, CheckConstraint, \
    ForeignKeyConstraint, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class TransactionDocuments(Base):
    __tablename__ = 'transaction_documents'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['tx_id'], ['transactions.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        CheckConstraint("status IN ('pending', 'confirmed')"),
    )

    id: uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    tx_id: uuid = Column(UUID(as_uuid=True), nullable=True)
    user_id: uuid = Column(UUID(as_uuid=True), nullable=False)
    original_filename: str = Column(String(256), nullable=False)
    mime_type: str = Column(String(100), nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    status: str = Column(String(20), nullable=False, default='pending')
    uploaded_at: datetime = Column(DateTime, nullable=False, default=datetime.now)
