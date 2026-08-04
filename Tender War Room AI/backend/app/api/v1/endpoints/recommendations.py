from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.models.user import User
from app.models.recommendation import BidRecommendation
from app.services.recommendation_service import recommendation_service

router = APIRouter()


@router.post("/{tender_id}", status_code=status.HTTP_200_OK)
async def generate_bid_recommendation(
    tender_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Triggers AI bid recommendations compiling similarity matching, competitor histories,
    and contractor markup sheets.
    """
    try:
        rec = await recommendation_service.generate_recommendation(db, tender_id)
        return rec
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate bidding recommendation: {str(e)}"
        )


@router.get("/{tender_id}", status_code=status.HTTP_200_OK)
async def get_bid_recommendation(
    tender_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Retrieves the persisted recommendation statistics for a tender.
    """
    stmt = select(BidRecommendation).filter(BidRecommendation.tender_id == tender_id)
    res = await db.execute(stmt)
    rec = res.scalars().first()
    
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bidding recommendation not found for this tender. Run POST to generate first."
        )
        
    # Reconstruct dictionary response
    # Re-calculate win probabilities based on mean fallback
    # In a real environment, we'd query similar logs, but here we can just rebuild.
    try:
        details = await recommendation_service.generate_recommendation(db, tender_id)
        return details
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
