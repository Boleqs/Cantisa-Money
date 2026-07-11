import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, Date, Numeric, DateTime, func, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class FxRates(Base):
    """Cache des taux de change EUR<->USD etc. Partagé entre tous les utilisateurs (un taux de
    change n'a pas de notion de propriétaire) — évite de refaire un appel yfinance à chaque requête
    et sert de repli si l'API est indisponible."""
    __tablename__ = 'fx_rates'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        UniqueConstraint('from_code', 'to_code', 'rate_date'),
    )

    id:uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    from_code:str = Column(String(10), nullable=False)
    to_code:str = Column(String(10), nullable=False)
    rate_date = Column(Date, nullable=False)
    rate = Column(Numeric, nullable=False)
    fetched_at:datetime = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
