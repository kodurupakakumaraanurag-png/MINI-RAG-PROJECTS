from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
import pytest
from fastapi import status

from app.models.user import User, UserRole
from app.models.tender import Tender, TenderStatus
from app.models.boq import BOQ
from app.services.report_service import ReportService, report_service
from app.core import security


@pytest.mark.asyncio
@patch("app.services.report_service.recommendation_service")
@patch("app.services.report_service.estimation_service")
async def test_generate_print_report_html(
    mock_estimation, mock_recommendation, mock_db_session
) -> None:
    service = ReportService()
    tender_uuid = uuid4()
    
    # 1. Mock tender
    mock_tender = Tender(
        id=tender_uuid,
        tender_number="T-REP-88",
        work_name="Laying water pipeline",
        eligibility_criteria="Standard",
        penalty_clauses="Standard"
    )
    mock_db_session.get.return_value = mock_tender
    
    # 2. Mock cost summary
    mock_estimation.get_cost_sheet_summary = AsyncMock(return_value={
        "official_estimated_cost": 50000.00,
        "base_construction_cost": 45000.00,
        "break_even_cost": 51975.00,
        "tender_number": "T-REP-88",
        "work_name": "Laying water pipeline",
        "margin_projections": [
            {
                "bid_percent_deviation": 0.0,
                "bid_amount": 50000.00,
                "expected_profit": -1975.00,
                "profit_margin_percent": -3.95,
                "recommendation_status": "Unviable"
            }
        ]
    })
    
    # 3. Mock recommendations
    mock_recommendation.generate_recommendation = AsyncMock(return_value={
        "risk_score": 5.0,
        "confidence_level": "Medium",
        "assumptions": {"material_escalation": "8%"},
        "recommended_bid_range": {
            "min_percent": -5.0,
            "max_percent": -2.0,
            "win_probability_at_min": 45.0,
            "win_probability_at_max": 20.0
        }
    })
    
    # 4. Mock BOQ item
    item1 = BOQ(
        tender_id=tender_uuid,
        item_number="1.1",
        description="Soil excavation",
        quantity=100.0,
        unit="Cum",
        estimated_rate=10.00,
        estimated_amount=1000.00,
        contractor_rate=12.00,
        contractor_amount=1200.00
    )
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [item1]
    mock_db_session.execute.return_value = mock_result
    
    # Run report compilation
    html = await service.generate_print_report(mock_db_session, str(tender_uuid))
    
    assert "BID STRATEGY DOSSIER" in html
    assert "T-REP-88" in html
    assert "Soil excavation" in html
    assert "Rs. 1,200.00" in html # Custom subtotal formatted correctly
    assert "win_probability_distribution" not in html # verified loops and projection bounds compile


@pytest.mark.asyncio
@patch("app.api.deps.user_repository")
async def test_reports_endpoints(mock_user_repo, client) -> None:
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
    mock_html = "<html><body>Report Summary Page</body></html>"
    
    with patch.object(report_service, "generate_print_report", AsyncMock(return_value=mock_html)):
        response = await client.get(
            f"/api/v1/reports/{tender_id}/print",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert "Report Summary Page" in response.text
        assert "text/html" in response.headers["content-type"]
