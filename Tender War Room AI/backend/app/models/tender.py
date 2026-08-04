import enum
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Numeric, Integer, DateTime, Boolean, ForeignKey, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import BaseUUID

if TYPE_CHECKING:
    from app.models.boq import BOQ
    from app.models.recommendation import BidRecommendation



class TenderStatus(str, enum.Enum):
    SCRAPED = "Scraped"
    EXTRACTED = "Extracted"
    ANALYZED = "Analyzed"
    BID_PREPARED = "Bid Prepared"
    SUBMITTED = "Submitted"
    WON = "Won"
    LOST = "Lost"


class Department(BaseUUID):
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    tenders: Mapped[List["Tender"]] = relationship("Tender", back_populates="department")


class Area(BaseUUID):
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(100), default="Telangana", nullable=False)

    tenders: Mapped[List["Tender"]] = relationship("Tender", back_populates="area")


class Tender(BaseUUID):
    tender_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    
    department_id: Mapped[Optional[str]] = mapped_column(ForeignKey("department.id"), nullable=True)
    area_id: Mapped[Optional[str]] = mapped_column(ForeignKey("area.id"), nullable=True)
    
    work_name: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_cost: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    emd: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    completion_period_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bidding_class: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    closing_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    opening_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    eligibility_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    defect_liability_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    penalty_clauses: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    raw_pdf_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[TenderStatus] = mapped_column(
        Enum(TenderStatus),
        default=TenderStatus.SCRAPED,
        nullable=False
    )

    department: Mapped[Optional[Department]] = relationship("Department", back_populates="tenders")
    area: Mapped[Optional[Area]] = relationship("Area", back_populates="tenders")
    documents: Mapped[List["TenderDocument"]] = relationship(
        "TenderDocument",
        back_populates="tender",
        cascade="all, delete-orphan"
    )
    boq_items: Mapped[List["BOQ"]] = relationship(
        "BOQ",
        back_populates="tender",
        cascade="all, delete-orphan"
    )
    recommendations: Mapped[List["BidRecommendation"]] = relationship(
        "BidRecommendation",
        back_populates="tender",
        cascade="all, delete-orphan"
    )



class TenderDocument(BaseUUID):
    tender_id: Mapped[str] = mapped_column(ForeignKey("tender.id"), nullable=False)
    
    document_type: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. "TenderNotice", "BOQ", "Corrigendum"
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False) # SHA-256 hash
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    downloaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    tender: Mapped[Tender] = relationship("Tender", back_populates="documents")
