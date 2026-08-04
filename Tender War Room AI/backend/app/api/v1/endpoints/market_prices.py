from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.services.market_service import market_service

router = APIRouter()


@router.get("/trends")
async def get_prices_trend(
    material_type: str,
    region: str = "Telangana",
    limit: int = 30,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Get pricing trends for a specific material and region.
    """
    trends = await market_service.get_price_trends(
        db, material_type=material_type, region=region, limit=limit
    )
    return trends


@router.get("/forecasts")
async def get_price_forecast(
    material_type: str,
    region: str = "Telangana",
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Retrieve price projection models for next month.
    """
    forecast = await market_service.generate_forecast(
        db, material_type=material_type, region=region
    )
    return forecast


@router.get("/alerts")
async def get_volatility_alerts(
    region: str = "Telangana",
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Check for materials exhibiting high price spikes/drops (>=10% change).
    """
    alerts = await market_service.get_volatility_alerts(db, region=region)
    return alerts
