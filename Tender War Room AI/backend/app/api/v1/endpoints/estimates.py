from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.services.estimation_service import estimation_service

router = APIRouter()


@router.put("/{tender_id}/boq-rates", status_code=status.HTTP_200_OK)
async def update_boq_rates(
    tender_id: str,
    rates: List[dict],
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Update customized bidding rates on BOQ lines.
    """
    try:
        updated = await estimation_service.update_boq_item_rates(db, tender_id, rates)
        return {"message": "BOQ rates updated successfully", "updated_items": updated}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update BOQ rates: {str(e)}"
        )


@router.post("/{tender_id}/calculate", status_code=status.HTTP_200_OK)
async def calculate_cost_sheet(
    tender_id: str,
    overhead_percent: float = 10.0,
    tax_percent: float = 5.0,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Calculate overheads, taxes, break-even costs, and margin models.
    """
    try:
        summary = await estimation_service.get_cost_sheet_summary(
            db, tender_id, overhead_percent=overhead_percent, tax_percent=tax_percent
        )
        return summary
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during calculations: {str(e)}"
        )
