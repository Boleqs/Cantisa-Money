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
        ForeignKeyConstraint(['operation_id'], ['asset_operations.id'], ondelete='SET NULL'),

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
    # Frais/commissions forfaitaires de cette vente, toujours en devise par défaut (Settings.currency)
    # — voir rt_assets.py::sell_possession, déduits du montant crédité et du gain réalisé.
    fees:int = Column(Numeric, nullable=False, default=0)
    # Taux de change effectivement appliqué à CETTE vente (devise de l'actif -> devise par défaut),
    # manuel ou résolu automatiquement — NULL si l'actif est dans la devise par défaut (aucune
    # conversion n'a de sens). Persisté pour la même raison qu'AssetPossession.fx_rate : ne pas
    # redépendre d'une résolution automatique implicite si les données de change évoluent plus tard.
    fx_rate:int = Column(Numeric, nullable=True)
    sale_date:datetime = Column(DateTime, nullable=False)
    dest_account_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    tx_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    source_split_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    dest_split_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    # Null si le lot cédé n'avait pas de purchase_price connu (coût d'acquisition inconnu).
    realized_gain:int = Column(Numeric, nullable=True)
    holding_period_days:int = Column(Integer, nullable=True)
    # Non nul si cette cession est la clôture synthétique d'un lot lors d'une fusion (voir
    # asset_operations.py et rt_assets.py::create_asset_operation) — realized_gain vaut alors 0
    # (rollover neutre) plutôt qu'un vrai gain/perte de marché. NULL pour une vente normale.
    operation_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    # Partagé par toutes les cessions issues d'un même appel à sell_possession (une vente FIFO peut
    # piocher sur plusieurs lots à la fois) — permet de modifier/supprimer LA vente en une fois plutôt
    # que lot par lot, voir rt_assets.py::_execute_sale. NULL pour une cession issue d'une opération
    # sur titre (operation_id non nul), qui n'est pas une vente éditable via ce mécanisme.
    sale_id:uuid = Column(UUID(as_uuid=True), nullable=True)
    created_at:datetime = Column(DateTime, default=func.current_timestamp())
