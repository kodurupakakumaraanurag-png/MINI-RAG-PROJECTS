import logging
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tender import Tender
from app.models.boq import BOQ

logger = logging.getLogger("app.estimation")


class EstimationService:
    async def update_boq_item_rates(
        self, db: AsyncSession, tender_id: str, rates: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Updates contractor bidding rates for specific items in a tender BOQ ledger.
        Expects rates as a list of dicts: [{'item_number': '1.1', 'contractor_rate': 125.50}, ...]
        """
        logger.info("Batch updating BOQ rates for tender: %s", tender_id)
        tender_uuid = UUID(tender_id)
        
        updated_items = []
        for rate_in in rates:
            item_no = rate_in.get("item_number")
            c_rate = rate_in.get("contractor_rate")
            if not item_no or c_rate is None:
                continue
                
            # Fetch item
            stmt = select(BOQ).filter(
                BOQ.tender_id == tender_uuid,
                BOQ.item_number == item_no
            )
            res = await db.execute(stmt)
            boq_item = res.scalars().first()
            if not boq_item:
                logger.warning("BOQ item %s not found for tender %s", item_no, tender_id)
                continue
                
            # Compute contractor subtotal
            c_rate_float = float(c_rate)
            boq_item.contractor_rate = c_rate_float
            boq_item.contractor_amount = float(boq_item.quantity) * c_rate_float
            
            db.add(boq_item)
            updated_items.append({
                "item_number": boq_item.item_number,
                "contractor_rate": float(boq_item.contractor_rate),
                "contractor_amount": float(boq_item.contractor_amount)
            })
            
        await db.commit()
        return updated_items

    async def get_cost_sheet_summary(
        self, db: AsyncSession, tender_id: str, overhead_percent: float = 10.0, tax_percent: float = 5.0
    ) -> Dict[str, Any]:
        """
        Generates base construction cost sheet summary, overhead compounding,
        tax applications, break-even costs, and bidding margin projections.
        """
        logger.info(
            "Generating cost sheet summary for %s (overheads: %.2f%%, tax: %.2f%%)",
            tender_id, overhead_percent, tax_percent
        )
        tender_uuid = UUID(tender_id)
        
        # Load tender
        tender = await db.get(Tender, tender_uuid)
        if not tender:
            raise ValueError(f"Tender with ID {tender_id} not found.")
            
        # Load BOQ items
        stmt = select(BOQ).filter(BOQ.tender_id == tender_uuid)
        res = await db.execute(stmt)
        boq_items = res.scalars().all()
        
        total_official_estimated = 0.0
        base_construction_cost = 0.0
        
        for item in boq_items:
            total_official_estimated += float(item.estimated_amount)
            if item.contractor_amount is not None:
                base_construction_cost += float(item.contractor_amount)
            else:
                # If not overridden, default to official estimated subtotal
                base_construction_cost += float(item.estimated_amount)
                
        # Calculations
        overhead_amount = base_construction_cost * (overhead_percent / 100.0)
        taxable_base = base_construction_cost + overhead_amount
        tax_amount = taxable_base * (tax_percent / 100.0)
        total_project_cost = taxable_base + tax_amount
        
        # Bidding margin projections (simulated bids from -15% to +10%)
        margin_projections = []
        for margin in [-10.0, -5.0, 0.0, 5.0, 10.0]:
            # Bid amount as deviation from official estimated cost (ECV)
            bid_amount = total_official_estimated * (1.0 + (margin / 100.0))
            expected_profit = bid_amount - total_project_cost
            expected_profit_margin_percent = (expected_profit / bid_amount) * 100 if bid_amount > 0 else 0.0
            
            margin_projections.append({
                "bid_percent_deviation": margin,
                "bid_amount": round(bid_amount, 2),
                "expected_profit": round(expected_profit, 2),
                "profit_margin_percent": round(expected_profit_margin_percent, 2),
                "recommendation_status": "Viable" if expected_profit > 0 else "Unviable (Below Cost)"
            })
            
        return {
            "tender_id": tender_id,
            "tender_number": tender.tender_number,
            "work_name": tender.work_name,
            "official_estimated_cost": total_official_estimated,
            "base_construction_cost": round(base_construction_cost, 2),
            "overhead_amount": round(overhead_amount, 2),
            "tax_amount": round(tax_amount, 2),
            "break_even_cost": round(total_project_cost, 2), # break-even equals total cost to contractor
            "margin_projections": margin_projections
        }


estimation_service = EstimationService()
