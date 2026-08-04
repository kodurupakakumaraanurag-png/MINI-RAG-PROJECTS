from typing import Optional
from sqlalchemy import String, Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import BaseUUID
from app.models.tender import Tender


class BOQ(BaseUUID):
    tender_id: Mapped[str] = mapped_column(ForeignKey("tender.id"), nullable=False)
    
    item_number: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(15, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    
    estimated_rate: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    estimated_amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    
    # Optional fields for contractor customizations
    contractor_rate: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    contractor_amount: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)

    tender: Mapped[Tender] = relationship("Tender", back_populates="boq_items")

