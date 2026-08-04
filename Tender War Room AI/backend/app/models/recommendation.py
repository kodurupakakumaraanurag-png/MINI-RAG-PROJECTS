from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import String, Numeric, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import BaseUUID
from app.models.tender import Tender


class Competitors(BaseUUID):
    company_name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    tender_type_preference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    historical_win_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True) # win rate e.g. 15.45%
    bidding_behavior_profile: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True) # JSON store for strategy notes


class BidRecommendation(BaseUUID):
    tender_id: Mapped[str] = mapped_column(ForeignKey("tender.id"), nullable=False)
    
    recommended_bid_range_min: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False) # e.g. -10.500 (% below)
    recommended_bid_range_max: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False) # e.g. -5.200 (% below)
    
    estimated_profit_min: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    estimated_profit_max: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    
    risk_score: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False) # e.g. 4.50 (scale of 0 to 10)
    confidence_level: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. "High", "Medium", "Low"
    
    similar_tenders_used: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True) # List of UUID strings
    assumptions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True) # JSON details of materials, labor prices assumed
    
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    tender: Mapped[Tender] = relationship("Tender", back_populates="recommendations")
