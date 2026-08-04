from datetime import date
from typing import Optional
from sqlalchemy import String, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base_class import BaseUUID


class MaterialPrices(BaseUUID):
    material_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False) # e.g. "Cement", "Steel", "Sand", "Diesel"
    price_per_unit: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. "Bag", "MT", "Brass", "Litre"
    region: Mapped[str] = mapped_column(String(100), default="Telangana", nullable=False)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)


class LabourRates(BaseUUID):
    labour_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False) # e.g. "Skilled", "Semi-Skilled", "Unskilled", "Operator"
    rate_per_day: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    region: Mapped[str] = mapped_column(String(100), default="Telangana", nullable=False)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)


class MachineRates(BaseUUID):
    machine_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False) # e.g. "Excavator", "Tipper", "Roller", "Mixer"
    rate_per_hour: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=False)
