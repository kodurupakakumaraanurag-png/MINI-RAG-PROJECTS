import enum
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Numeric, Integer, DateTime, Boolean, ForeignKey, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import BaseUUID


class BidStatus(str, enum.Enum):
    WON = "Won"
    LOST = "Lost"
    DISQUALIFIED = "Disqualified"


class Contractor(BaseUUID):
    company_name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    registration_class: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rating: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True) # 0.00 to 5.00

    bids: Mapped[List["HistoricalBid"]] = relationship("HistoricalBid", back_populates="contractor")
    awards: Mapped[List["Award"]] = relationship("Award", back_populates="contractor")
    winning_tenders: Mapped[List["HistoricalTender"]] = relationship("HistoricalTender", back_populates="winner")


class HistoricalTender(BaseUUID):
    tender_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    work_name: Mapped[str] = mapped_column(Text, nullable=False)
    
    department_id: Mapped[Optional[str]] = mapped_column(ForeignKey("department.id"), nullable=True)
    
    estimated_cost: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    winning_bid_amount: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    winning_bid_percent_diff: Mapped[Optional[float]] = mapped_column(Numeric(6, 3), nullable=True) # e.g. -5.421 (percent below) or 3.120 (percent above)
    
    winning_contractor_id: Mapped[Optional[str]] = mapped_column(ForeignKey("contractor.id"), nullable=True)
    
    opening_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_period_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    winner: Mapped[Optional[Contractor]] = relationship("Contractor", back_populates="winning_tenders")
    bids: Mapped[List["HistoricalBid"]] = relationship("HistoricalBid", back_populates="historical_tender", cascade="all, delete-orphan")
    award: Mapped[Optional["Award"]] = relationship("Award", uselist=False, back_populates="historical_tender")


class HistoricalBid(BaseUUID):
    historical_tender_id: Mapped[str] = mapped_column(ForeignKey("historical_tender.id"), nullable=False)
    contractor_id: Mapped[str] = mapped_column(ForeignKey("contractor.id"), nullable=False)
    
    bid_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    bid_percent_diff: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False) # percent deviation from ECV
    bid_rank: Mapped[int] = mapped_column(Integer, nullable=False) # e.g. L1, L2, L3... (1, 2, 3)
    bid_status: Mapped[BidStatus] = mapped_column(Enum(BidStatus), nullable=False)
    
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    historical_tender: Mapped[HistoricalTender] = relationship("HistoricalTender", back_populates="bids")
    contractor: Mapped[Contractor] = relationship("Contractor", back_populates="bids")


class Award(BaseUUID):
    historical_tender_id: Mapped[str] = mapped_column(ForeignKey("historical_tender.id"), unique=True, nullable=False)
    contractor_id: Mapped[str] = mapped_column(ForeignKey("contractor.id"), nullable=False)
    
    award_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    award_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    loi_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    historical_tender: Mapped[HistoricalTender] = relationship("HistoricalTender", back_populates="award")
    contractor: Mapped[Contractor] = relationship("Contractor", back_populates="awards")
