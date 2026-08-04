from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.services.simulation_service import simulation_service

router = APIRouter()


@router.post("/{tender_id}/run", status_code=status.HTTP_200_OK)
async def run_simulation(
    tender_id: str,
    material_multiplier: float = 0.0,
    labour_multiplier: float = 0.0,
    proposed_bid_deviation: float = 0.0,
    overhead_percent: float = 10.0,
    tax_percent: float = 5.0,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Run cost estimation sensitivity simulations and calculate bidding win probabilities.
    """
    try:
        sim_res = await simulation_service.run_whatif_simulation(
            db,
            tender_id=tender_id,
            material_multiplier=material_multiplier,
            labour_multiplier=labour_multiplier,
            proposed_bid_deviation=proposed_bid_deviation,
            overhead_percent=overhead_percent,
            tax_percent=tax_percent
        )
        return sim_res
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"What-If simulation run failed: {str(e)}"
        )
