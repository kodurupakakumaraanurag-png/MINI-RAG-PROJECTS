from datetime import date, timedelta, datetime, timezone
from uuid import uuid4
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
from fastapi import status

from app.models.user import User, UserRole
from app.models.market import MaterialPrices
from app.services.market_service import MarketService, market_service
from app.core import security


@pytest.mark.asyncio
async def test_get_price_trends(mock_db_session) -> None:
    service = MarketService()
    
    # Mock price records
    p1 = MaterialPrices(
        id=uuid4(),
        material_type="Cement",
        price_per_unit=350.00,
        unit="Bag",
        region="Telangana",
        recorded_date=date.today() - timedelta(days=5)
    )
    p2 = MaterialPrices(
        id=uuid4(),
        material_type="Cement",
        price_per_unit=360.00,
        unit="Bag",
        region="Telangana",
        recorded_date=date.today()
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [p2, p1] # returned out of order (desc)
    mock_db_session.execute.return_value = mock_result
    
    trends = await service.get_price_trends(mock_db_session, "Cement")
    
    assert len(trends) == 2
    # Verify chronological sorting (oldest first)
    assert trends[0]["recorded_date"] == (date.today() - timedelta(days=5)).isoformat()
    assert trends[1]["recorded_date"] == date.today().isoformat()
    assert trends[0]["price_per_unit"] == 350.00
    assert trends[1]["price_per_unit"] == 360.00


@pytest.mark.asyncio
async def test_generate_forecast_insufficient_data(mock_db_session) -> None:
    service = MarketService()
    
    p = MaterialPrices(
        id=uuid4(),
        material_type="Cement",
        price_per_unit=350.00,
        unit="Bag",
        region="Telangana",
        recorded_date=date.today()
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [p]
    mock_db_session.execute.return_value = mock_result
    
    res = await service.generate_forecast(mock_db_session, "Cement")
    assert "Insufficient historical data" in res["status"]


@pytest.mark.asyncio
async def test_generate_forecast_success(mock_db_session) -> None:
    service = MarketService()
    
    # Create linear upward trend (350, 360, 370)
    p1 = MaterialPrices(
        id=uuid4(),
        material_type="Cement",
        price_per_unit=350.00,
        unit="Bag",
        region="Telangana",
        recorded_date=date.today() - timedelta(days=10)
    )
    p2 = MaterialPrices(
        id=uuid4(),
        material_type="Cement",
        price_per_unit=360.00,
        unit="Bag",
        region="Telangana",
        recorded_date=date.today() - timedelta(days=5)
    )
    p3 = MaterialPrices(
        id=uuid4(),
        material_type="Cement",
        price_per_unit=370.00,
        unit="Bag",
        region="Telangana",
        recorded_date=date.today()
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [p3, p2, p1]
    mock_db_session.execute.return_value = mock_result
    
    res = await service.generate_forecast(mock_db_session, "Cement")
    
    assert res["status"] == "Success"
    assert res["latest_recorded_price"] == 370.00
    # Price is rising by 2 Rs per day. 30 days projection = 370 + (2 * 30) = 430
    assert res["forecasted_price"] == 430.00


@pytest.mark.asyncio
async def test_get_volatility_alerts_none(mock_db_session) -> None:
    service = MarketService()
    
    # Setup two mock material prices with very low change (less than 10%)
    p_now = MaterialPrices(
        material_type="Cement",
        price_per_unit=350.00,
        region="Telangana",
        recorded_date=date.today()
    )
    p_past = MaterialPrices(
        material_type="Cement",
        price_per_unit=348.00,
        region="Telangana",
        recorded_date=date.today() - timedelta(days=32)
    )
    
    # Mock distinct types call
    mock_distinct = MagicMock()
    mock_distinct.scalars.return_value.all.return_value = ["Cement"]
    
    # Mock latest item call
    mock_latest = MagicMock()
    mock_latest.scalars.return_value.first.return_value = p_now
    
    # Mock past item call
    mock_past = MagicMock()
    mock_past.scalars.return_value.first.return_value = p_past
    
    mock_db_session.execute.side_effect = [mock_distinct, mock_latest, mock_past]
    
    alerts = await service.get_volatility_alerts(mock_db_session)
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_get_volatility_alerts_triggered(mock_db_session) -> None:
    service = MarketService()
    
    # Setup two mock material prices with high change (cement jumps from 300 to 450, a 50% shift)
    p_now = MaterialPrices(
        material_type="Cement",
        price_per_unit=450.00,
        region="Telangana",
        recorded_date=date.today()
    )
    p_past = MaterialPrices(
        material_type="Cement",
        price_per_unit=300.00,
        region="Telangana",
        recorded_date=date.today() - timedelta(days=32)
    )
    
    mock_distinct = MagicMock()
    mock_distinct.scalars.return_value.all.return_value = ["Cement"]
    
    mock_latest = MagicMock()
    mock_latest.scalars.return_value.first.return_value = p_now
    
    mock_past = MagicMock()
    mock_past.scalars.return_value.first.return_value = p_past
    
    mock_db_session.execute.side_effect = [mock_distinct, mock_latest, mock_past]
    
    alerts = await service.get_volatility_alerts(mock_db_session)
    assert len(alerts) == 1
    assert alerts[0]["material_type"] == "Cement"
    assert alerts[0]["percent_change"] == 50.00
    assert alerts[0]["alert_level"] == "High"


@pytest.mark.asyncio
@patch("app.api.deps.user_repository")
async def test_market_prices_endpoints(mock_user_repo, client) -> None:
    user_uuid = uuid4()
    mock_user = User(
        id=user_uuid,
        username="john",
        email="john@example.com",
        role=UserRole.CONTRACTOR,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    mock_user_repo.get = AsyncMock(return_value=mock_user)
    token = security.create_access_token(subject=user_uuid)
    
    mock_trends = [{"recorded_date": "2026-08-01", "price_per_unit": 350.0}]
    mock_forecast = {"status": "Success", "forecasted_price": 360.0}
    mock_alerts = [{"material_type": "Steel", "percent_change": 12.0}]
    
    with patch.object(market_service, "get_price_trends", AsyncMock(return_value=mock_trends)):
        with patch.object(market_service, "generate_forecast", AsyncMock(return_value=mock_forecast)):
            with patch.object(market_service, "get_volatility_alerts", AsyncMock(return_value=mock_alerts)):
                # 1. Trends
                response = await client.get(
                    "/api/v1/market-prices/trends?material_type=Cement",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert response.status_code == status.HTTP_200_OK
                assert response.json() == mock_trends
                
                # 2. Forecasts
                response = await client.get(
                    "/api/v1/market-prices/forecasts?material_type=Cement",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert response.status_code == status.HTTP_200_OK
                assert response.json() == mock_forecast
                
                # 3. Alerts
                response = await client.get(
                    "/api/v1/market-prices/alerts",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert response.status_code == status.HTTP_200_OK
                assert response.json() == mock_alerts
