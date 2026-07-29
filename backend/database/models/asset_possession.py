import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKey, CheckConstraint, SmallInteger, \
    UniqueConstraint, PrimaryKeyConstraint, ForeignKeyConstraint, Numeric
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class AssetPossession(Base):
    __tablename__ = 'asset_possession'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE', onupdate='CASCADE'),
        ForeignKeyConstraint(['source_account_id'], ['accounts.id'], ondelete='SET NULL', onupdate='CASCADE'),
        ForeignKeyConstraint(['tx_id'], ['transactions.id'], ondelete='SET NULL'),
        ForeignKeyConstraint(['source_split_id'], ['splits.id'], ondelete='SET NULL'),
        ForeignKeyConstraint(['dest_split_id'], ['splits.id'], ondelete='SET NULL'),
        ForeignKeyConstraint(['dca_plan_id'], ['dca_plans.id'], ondelete='SET NULL'),

        CheckConstraint("quantity <= 1000000000 AND quantity >= 0", name='asset_possession_quantity_check')
    )

    user_id:uuid = Column(UUID(as_uuid=True))
    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    asset_id:uuid = Column(UUID(as_uuid=True))
    account_id:uuid = Column(UUID(as_uuid=True))
    source_account_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    tx_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    source_split_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    dest_split_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    # Non nul si ce lot provient d'une exécution de plan DCA (voir dca_plans.py) — permet de
    # retrouver les lots générés par un plan sans dépendre du texte de la description.
    dca_plan_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    quantity = Column(Numeric(18, 6), nullable=False, default=0)
    purchase_price:int = Column(Numeric, nullable=True)
    purchase_price_native:int = Column(Numeric, nullable=True)
    purchase_date:datetime = Column(DateTime, nullable=True)
    created_at:datetime = Column(DateTime, default=func.current_timestamp())