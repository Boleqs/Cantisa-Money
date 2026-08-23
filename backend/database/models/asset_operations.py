import uuid

from .base import Base
from datetime import datetime, date
from sqlalchemy import Column, String, Date, DateTime, Numeric, PrimaryKeyConstraint, \
    ForeignKeyConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class AssetOperations(Base):
    """Opération sur titre décidée par l'émetteur (split/regroupement, fusion, scission) —
    voir rt_assets.py pour l'application effective aux lots (AssetPossession/AssetDisposal),
    portfolio_ops.py::cost_basis_per_unit pour le calcul du coût de revient partagé avec le
    frontend (Portfolio.vue::costBasisPerUnit)."""
    __tablename__ = 'asset_operations'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['target_asset_id'], ['assets.id'], ondelete='SET NULL'),
        CheckConstraint("operation_type IN ('split', 'merger', 'spinoff')"),
        CheckConstraint("ratio_from > 0 AND ratio_to > 0"),
        CheckConstraint("cost_allocation_pct IS NULL OR (cost_allocation_pct >= 0 AND cost_allocation_pct <= 100)"),
    )

    id: uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    user_id: uuid = Column(UUID(as_uuid=True), nullable=False)
    asset_id: uuid = Column(UUID(as_uuid=True), nullable=False)
    operation_type: str = Column(String(20), nullable=False)
    operation_date: date = Column(Date, nullable=False)
    # "Pour ratio_from part(s) détenue(s), on obtient ratio_to part(s)" — ex: split 4-pour-1 =>
    # ratio_from=1, ratio_to=4. Pour merger/spinoff, s'applique à la quantité reçue sur target_asset_id.
    ratio_from: int = Column(Numeric, nullable=False)
    ratio_to: int = Column(Numeric, nullable=False)
    # NULL pour un split (rescale en place) ; obligatoire pour merger/spinoff (validé côté route) —
    # l'actif cible doit déjà exister (pas de création inline, cf. rt_assets.py::create_asset_operation).
    target_asset_id: uuid = Column(UUID(as_uuid=True), nullable=True)
    # Uniquement pour spinoff : part du prix de revient de l'actif source transférée vers l'actif
    # cible (0-100). Ne peut pas être déduit automatiquement (dépend de valeurs de marché externes
    # au moment de l'opération) — saisi par l'utilisateur.
    cost_allocation_pct: int = Column(Numeric, nullable=True)
    note: str = Column(String(255), nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.now, nullable=False)
