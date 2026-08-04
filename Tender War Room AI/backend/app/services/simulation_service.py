import logging
from typing import Any, Dict
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.estimation_service import estimation_service
from app.services.similarity_service import similarity_service
from app.services.recommendation_service import recommendation_service

logger = logging.getLogger("app.simulation")


class SimulationService:
    async def run_whatif_simulation(
        self,
        db: AsyncSession,
        tender_id: str,
        material_multiplier: float = 0.0,
        labour_multiplier: float = 0.0,
        proposed_bid_deviation: float = 0.0,
        overhead_percent: float = 10.0,
        tax_percent: float = 5.0
    ) -> Dict[str, Any]:
        """
        Simulates the cost and bidding impact of fluctuations in material prices and labour rates.
        Applies a standard civil contracting resource ratio: 60% Materials, 40% Labour.
        """
        logger.info(
            "Running what-if simulation for tender %s (materials change: %.2f%%, labour change: %.2f%%)",
            tender_id, material_multiplier, labour_multiplier
        )
        
        # 1. Fetch original cost estimate summary
        cost_sheet = await estimation_service.get_cost_sheet_summary(
            db, tender_id, overhead_percent=overhead_percent, tax_percent=tax_percent
        )
        
        original_bcc = cost_sheet["base_construction_cost"]
        official_cost = cost_sheet["official_estimated_cost"]
        original_break_even = cost_sheet["break_even_cost"]
        
        # 2. Compute simulated base construction cost using resource split ratios
        mat_factor = 0.60 * (1.0 + (material_multiplier / 100.0))
        lab_factor = 0.40 * (1.0 + (labour_multiplier / 100.0))
        sim_bcc = original_bcc * (mat_factor + lab_factor)
        
        # 3. Compute simulated overhead, tax and compounded break-even cost
        sim_overhead = sim_bcc * (overhead_percent / 100.0)
        sim_taxable_base = sim_bcc + sim_overhead
        sim_tax = sim_taxable_base * (tax_percent / 100.0)
        sim_break_even = sim_taxable_base + sim_tax
        
        # 4. Compute proposed bid stats
        proposed_bid_amount = official_cost * (1.0 + (proposed_bid_deviation / 100.0))
        sim_profit = proposed_bid_amount - sim_break_even
        sim_margin = (sim_profit / proposed_bid_amount) * 100 if proposed_bid_amount > 0 else 0.0
        
        # 5. Compute win probability under proposed bid deviation
        rec_service_res = await similarity_service.search_similar_tenders(
            db, query_text=cost_sheet["work_name"], limit=5
        )
        
        similar_results = rec_service_res["results"]
        winning_deviations = [
            r["winning_bid_percent_diff"]
            for r in similar_results
            if r["winning_bid_percent_diff"] is not None
        ]
        
        if not winning_deviations:
            # तेलंगाना eProcurement fallback deviations
            winning_deviations = [-4.0, -6.0, -8.0]
            
        mean_dev = float(np.mean(winning_deviations))
        std_dev = float(np.std(winning_deviations)) if len(winning_deviations) > 1 else 2.0
        if std_dev == 0.0:
            std_dev = 2.0
            
        win_prob = recommendation_service.calculate_win_probability(
            proposed_bid_deviation, mean_dev, std_dev
        )
        
        return {
            "tender_id": tender_id,
            "tender_number": cost_sheet["tender_number"],
            "work_name": cost_sheet["work_name"],
            "official_estimated_cost": official_cost,
            "original_break_even": original_break_even,
            "simulated_break_even": round(sim_break_even, 2),
            "simulated_cost_increase_percent": round(((sim_break_even - original_break_even) / original_break_even) * 100, 2) if original_break_even > 0 else 0.0,
            "proposed_bid": {
                "deviation_percent": proposed_bid_deviation,
                "amount": round(proposed_bid_amount, 2),
                "simulated_profit": round(sim_profit, 2),
                "simulated_profit_margin_percent": round(sim_margin, 2),
                "win_probability_percent": round(win_prob * 100, 2)
            },
            "viability_status": "Viable" if sim_profit > 0 else "Unviable (Bid Below Cost)"
        }


simulation_service = SimulationService()
