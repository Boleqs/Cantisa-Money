import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, func, CheckConstraint, \
    PrimaryKeyConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class AssetDisposal(Base):
    __tablename__ = 'asset_disposal'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['possession_id'], ['asset_possession.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['dest_account_id'], ['accounts.id'], ondelete='SET NULL', onupdate='CASCADE'),
        ForeignKeyConstraint(['tx_id'], ['transactions.id'], ondelete='SET NULL'),
        ForeignKeyConstraint(['source_split_id'], ['splits.id'], ondelete='SET NULL'),
        ForeignKeyConstraint(['dest_split_id'], ['splits.id'], ondelete='SET NULL'),

        CheckConstraint("quantity <= 1000000000 AND quantity >= 0", name='ck_asset_disposal_quantity'),
    )

    user_id:uuid = Column(UUID(as_uuid=True))
    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    possession_id:uuid = Column(UUID(as_uuid=True))
    # Quantité cédée par CETTE vente (pas la quantité restante du lot, qui se déduit en sommant
    # toutes les cessions liées à un possession_id — voir _remaining_quantity_as_of dans wealth.py).
    quantity = Column(Numeric(18, 6), nullable=False, default=0)
    sale_price:int = Column(Numeric, nullable=True)
    sale_price_native:int = Column(Numeric, nullable=True)
    sale_date:datetime = Column(DateTime, nullable=False)
    dest_account_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    tx_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    source_split_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    dest_split_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    # Null si le lot cédé n'avait pas de purchase_price connu (coût d'acquisition inconnu).
    realized_gain:int = Column(Numeric, nullable=True)
    holding_period_days:int = Column(Integer, nullable=True)
    created_at:datetime = Column(DateTime, default=func.current_timestamp())
