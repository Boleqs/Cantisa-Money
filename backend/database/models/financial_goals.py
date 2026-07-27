import uuid
from .base import Base
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Numeric, PrimaryKeyConstraint, ForeignKeyConstraint, \
    CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from dataclasses import dataclass


@dataclass
class FinancialGoals(Base):
    """Objectif de vie (achat immobilier, études, retraite...) confronté à la projection de
    patrimoine — voir project_wealth() dans utils/forecast.py, qui applique le retrait de chaque
    objectif sur la trésorerie projetée et signale s'il reste couvert."""
    __tablename__ = 'financial_goals'
    __table_args__ = (
        PrimaryKeyConstraint('id'),
        ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        CheckConstraint("goal_type IN ('one_time', 'recurring')"),
        CheckConstraint("target_amount > 0"),
    )

    user_id: uuid = Column(UUID(as_uuid=True))
    id: uuid = Column(UUID(as_uuid=True), default=uuid.uuid4)
    name: str = Column(String(128), nullable=False)
    # 'one_time' : besoin ponctuel (apport immobilier...) retiré une fois à target_date.
    # 'recurring' : retrait mensuel de target_amount démarrant à target_date, jusqu'à end_date
    # (ou jusqu'à la fin de l'horizon simulé si end_date est vide — ex. train de vie en retraite).
    goal_type: str = Column(String(16), nullable=False, default='one_time')
    target_amount: int = Column(Numeric, nullable=False)
    target_date: datetime = Column(DateTime, nullable=False)
    end_date: datetime = Column(DateTime, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.now())
    updated_at: datetime = Column(DateTime, default=datetime.now(), onupdate=datetime.now())
