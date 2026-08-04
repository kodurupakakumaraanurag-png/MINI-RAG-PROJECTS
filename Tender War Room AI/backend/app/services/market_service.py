import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import MaterialPrices, LabourRates, MachineRates

logger = logging.getLogger("app.market")


class MarketService:
    async def get_price_trends(
        self, db: AsyncSession, material_type: str, region: str = "Telangana", limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Retrieves pricing logs for a material sorted chronologically.
        """
        logger.info("Fetching price trends for %s in %s", material_type, region)
        result = await db.execute(
            select(MaterialPrices)
            .filter(
                MaterialPrices.material_type.ilike(material_type),
                MaterialPrices.region.ilike(region)
            )
            .order_by(desc(MaterialPrices.recorded_date))
            .limit(limit)
        )
        prices = result.scalars().all()
        # Return sorted chronologically for charting
        return sorted([
            {
                "id": str(p.id),
                "material_type": p.material_type,
                "price_per_unit": float(p.price_per_unit),
                "unit": p.unit,
                "region": p.region,
                "recorded_date": p.recorded_date.isoformat()
            }
            for p in prices
        ], key=lambda x: x["recorded_date"])

    async def generate_forecast(
        self, db: AsyncSession, material_type: str, region: str = "Telangana"
    ) -> Dict[str, Any]:
        """
        Projects next month's material price using a simple numpy polyfit linear regression.
        """
        logger.info("Generating next-month forecast for %s in %s", material_type, region)
        result = await db.execute(
            select(MaterialPrices)
            .filter(
                MaterialPrices.material_type.ilike(material_type),
                MaterialPrices.region.ilike(region)
            )
            .order_by(desc(MaterialPrices.recorded_date))
            .limit(10)
        )
        prices = result.scalars().all()
        if len(prices) < 2:
            return {
                "material_type": material_type,
                "region": region,
                "status": "Insufficient historical data for forecasting"
            }

        # Order chronologically for calculations
        prices = sorted(prices, key=lambda x: x.recorded_date)
        
        # Build training points: x = date ordinals, y = price values
        x = [p.recorded_date.toordinal() for p in prices]
        y = [float(p.price_per_unit) for p in prices]
        
        # Fit linear regression model
        slope, intercept = np.polyfit(x, y, 1)
        
        # Project 30 days ahead from the latest date
        latest_date = prices[-1].recorded_date
        target_date = latest_date + timedelta(days=30)
        forecast_price = float(slope * target_date.toordinal() + intercept)
        
        # Clean negative numbers in extreme downward slopes
        forecast_price = max(0.01, forecast_price)
        
        # Calculate historical volatility range (standard deviation)
        volatility = float(np.std(y))
        
        return {
            "material_type": material_type,
            "region": region,
            "latest_recorded_price": float(prices[-1].price_per_unit),
            "latest_recorded_date": latest_date.isoformat(),
            "forecasted_price": round(forecast_price, 2),
            "forecast_date": target_date.isoformat(),
            "volatility_margin": round(volatility, 2),
            "status": "Success"
        }

    async def get_volatility_alerts(
        self, db: AsyncSession, region: str = "Telangana"
    ) -> List[Dict[str, Any]]:
        """
        Detects materials exhibiting extreme price change (>10%) within a 30-day window.
        """
        logger.info("Evaluating volatility alerts for region: %s", region)
        alerts = []
        
        # Discover all unique material types recorded
        types_res = await db.execute(
            select(MaterialPrices.material_type)
            .filter(MaterialPrices.region.ilike(region))
            .distinct()
        )
        material_types = types_res.scalars().all()
        
        for m_type in material_types:
            # Get latest price
            latest_res = await db.execute(
                select(MaterialPrices)
                .filter(
                    MaterialPrices.material_type == m_type,
                    MaterialPrices.region.ilike(region)
                )
                .order_by(desc(MaterialPrices.recorded_date))
                .limit(1)
            )
            latest = latest_res.scalars().first()
            if not latest:
                continue
                
            # Get historical price around 30 days ago
            target_past_date = latest.recorded_date - timedelta(days=30)
            past_res = await db.execute(
                select(MaterialPrices)
                .filter(
                    MaterialPrices.material_type == m_type,
                    MaterialPrices.region.ilike(region),
                    MaterialPrices.recorded_date <= target_past_date
                )
                .order_by(desc(MaterialPrices.recorded_date))
                .limit(1)
            )
            past = past_res.scalars().first()
            if not past:
                continue
                
            p_latest = float(latest.price_per_unit)
            p_past = float(past.price_per_unit)
            
            # Calculate percent deviation
            percent_change = ((p_latest - p_past) / p_past) * 100
            
            if abs(percent_change) >= 10.0:
                alerts.append({
                    "material_type": m_type,
                    "region": region,
                    "previous_price": p_past,
                    "previous_recorded_date": past.recorded_date.isoformat(),
                    "current_price": p_latest,
                    "current_recorded_date": latest.recorded_date.isoformat(),
                    "percent_change": round(percent_change, 2),
                    "alert_level": "High" if abs(percent_change) >= 20.0 else "Medium",
                    "message": f"High volatility warning: {m_type} prices shifted by {percent_change:.2f}% since last month."
                })
                
        return alerts


market_service = MarketService()
