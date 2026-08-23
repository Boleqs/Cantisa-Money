import uuid

from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, func, ForeignKeyConstraint, UniqueConstraint, \
    PrimaryKeyConstraint, Numeric, CheckConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass

@dataclass
class Assets(Base):
    __tablename__ = 'assets'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        ForeignKeyConstraint(['commodity_id'], ['commodities.id'], ondelete='CASCADE'),

        UniqueConstraint('name', 'asset_type', 'commodity_id'),
        CheckConstraint("asset_type IN ('Stock', 'ETF', 'RealEstate', 'Vehicle', 'Other')"),
        CheckConstraint("asset_type IN ('Stock', 'ETF') OR sector IS NULL"),
        CheckConstraint("asset_type NOT IN ('Stock', 'ETF') OR country IS NULL"),
        CheckConstraint("track_live_price = false OR asset_type IN ('Stock', 'ETF')")
    )

    user_id:uuid = Column(UUID(as_uuid=True))
    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    symbol:str = Column(String(20), nullable=False)
    name:str = Column(String(100), nullable=False)
    asset_type:str = Column(String(20), nullable=False)
    sector:str = Column(String(50), nullable=True)
    # Uniquement pour les actifs physiques (RealEstate/Vehicle/Other) — pour Stock/ETF, la géographie
    # est déjà dérivée dynamiquement via Yahoo Finance (voir asset_geography.py), pas de saisie
    # manuelle nécessaire. Nom de pays en anglais (convention yfinance) pour fusionner correctement
    # avec cette source dans /api/assets/geography sans dupliquer un même pays sous deux libellés.
    country:str = Column(String(100), nullable=True)
    commodity_id:uuid = Column(UUID(as_uuid=True))
    value_per_unit:int = Column(Numeric, default=0, nullable=False)
    track_live_price:bool = Column(Boolean, default=False, nullable=False)
    last_price_updated_at:datetime = Column(DateTime, nullable=True)
    created_at:datetime = Column(DateTime, default=datetime.now(), nullable=False)

