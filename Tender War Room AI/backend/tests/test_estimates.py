from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
import pytest
from fastapi import status

from app.models.user import User, UserRole
from app.models.tender import Tender, TenderStatus
from app.models.boq import BOQ
from app.services.estimation_service import EstimationService, estimation_service
from app.core import security


@pytest.mark.asyncio
async def test_update_boq_item_rates(mock_db_session) -> None:
    service = EstimationService()
    tender_uuid = uuid4()
    
    # Create mock BOQ item
    item1 = BOQ(
        tender_id=tender_uuid,
        item_number="1.1",
        description="Laying concrete",
        quantity=50.0,
        unit="Cum",
        estimated_rate=100.0,
        estimated_amount=5000.0,
        contractor_rate=None,
        contractor_amount=None
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = item1
    mock_db_session.execute.return_value = mock_result
    
    # Run update
    rates_in = [{"item_number": "1.1", "contractor_rate": 90.00}]
    updated = await service.update_boq_item_rates(mock_db_session, str(tender_uuid), rates_in)
    
    assert len(updated) == 1
    assert updated[0]["item_number"] == "1.1"
    assert updated[0]["contractor_rate"] == 90.00
    assert updated[0]["contractor_amount"] == 4500.00 # 50.0 * 90.0
    
    assert item1.contractor_rate == 90.00
    assert item1.contractor_amount == 4500.00


@pytest.mark.asyncio
@patch("app.services.estimation_service.select")
async def test_get_cost_sheet_summary_math(mock_select, mock_db_session) -> None:
    service = EstimationService()
    tender_uuid = uuid4()
    
    # Mock tender
    mock_tender = Tender(
        id=tender_uuid,
        tender_number="T-EST-99",
        work_name="Pipeline lay",
        status=TenderStatus.SCRAPED
    )
    mock_db_session.get.return_value = mock_tender
    
    # Mock BOQ items (one overridden, one default)
    item1 = BOQ(
        tender_id=tender_uuid,
        item_number="1",
        description="Excavation",
        quantity=10.0,
        unit="Cum",
        estimated_rate=100.00,
        estimated_amount=1000.00,
        contractor_rate=120.00,
        contractor_amount=1200.00 # custom override
    )
    item2 = BOQ(
        tender_id=tender_uuid,
        item_number="2",
        description="Concrete",
        quantity=50.0,
        unit="Cum",
        estimated_rate=100.00,
        estimated_amount=5000.00,
        contractor_rate=None,
        contractor_amount=None # no override, fallback to 5000.00
    )
    
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [item1, item2]
    mock_db_session.execute.return_value = mock_result
    
    # Run calculation: 10% overhead, 5% tax
    # Base cost = 1200 (overridden) + 5000 (default fallback) = 6200
    # Overheads = 6200 * 0.10 = 620
    # Taxable Base = 6820
    # Tax = 6820 * 0.05 = 341
    # Break-even cost = 6820 + 341 = 7161
    res = await service.get_cost_sheet_summary(
        mock_db_session, str(tender_uuid), overhead_percent=10.0, tax_percent=5.0
    )
    
    assert res["tender_number"] == "T-EST-99"
    assert res["official_estimated_cost"] == 6000.00 # 1000 + 5000
    assert res["base_construction_cost"] == 6200.00
    assert res["overhead_amount"] == 620.00
    assert res["tax_amount"] == 341.00
    assert res["break_even_cost"] == 7161.00
    
    # Assert margin projections
    assert len(res["margin_projections"]) == 5
    # Deviation 0.0% means bidding exactly at official cost (6000.00)
    dev_0 = [m for m in res["margin_projections"] if m["bid_percent_deviation"] == 0.0][0]
    assert dev_0["bid_amount"] == 6000.00
    assert dev_0["expected_profit"] == 6000.00 - 7161.00 # -1161.00
    assert dev_0["recommendation_status"] == "Unviable (Below Cost)"


@pytest.mark.asyncio
@patch("app.api.deps.user_repository")
async def test_estimates_endpoints(mock_user_repo, client) -> None:
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
    
    tender_id = str(uuid4())
    mock_updated = [{"item_number": "1.1", "contractor_rate": 90.0}]
    mock_summary = {"tender_id": tender_id, "break_even_cost": 7161.0}
    
    with patch.object(estimation_service, "update_boq_item_rates", AsyncMock(return_value=mock_updated)):
        with patch.object(estimation_service, "get_cost_sheet_summary", AsyncMock(return_value=mock_summary)):
            # 1. Update rates
            response = await client.put(
                f"/api/v1/estimates/{tender_id}/boq-rates",
                json=[{"item_number": "1.1", "contractor_rate": 90.0}],
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["updated_items"] == mock_updated
            
            # 2. Calculate estimates
            response = await client.post(
                f"/api/v1/estimates/{tender_id}/calculate?overhead_percent=10.0&tax_percent=5.0",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["break_even_cost"] == 7161.0
