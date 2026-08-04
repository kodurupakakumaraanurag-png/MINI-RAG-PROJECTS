from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
import pytest
from fastapi import status

from app.models.user import User, UserRole
from app.models.tender import Tender, TenderStatus
from app.services.simulation_service import SimulationService, simulation_service
from app.core import security


@pytest.mark.asyncio
@patch("app.services.simulation_service.recommendation_service")
@patch("app.services.simulation_service.similarity_service")
@patch("app.services.simulation_service.estimation_service")
async def test_run_whatif_simulation_math(
    mock_estimation, mock_similarity, mock_rec_service, mock_db_session
) -> None:
    service = SimulationService()
    tender_uuid = uuid4()
    
    # 1. Mock original cost sheet: Base BCC = 100,000, Official ECV = 120,000
    mock_estimation.get_cost_sheet_summary = AsyncMock(return_value={
        "tender_number": "T-SIM-01",
        "work_name": "Excavation and lining",
        "official_estimated_cost": 120000.00,
        "base_construction_cost": 100000.00,
        "break_even_cost": 115500.00 # Base 100,000 + 10% overhead = 110,000; + 5% tax = 115,500
    })
    
    # 2. Mock similarity search (similar bids are: mean -6.0%, std 2.0%)
    mock_similarity.search_similar_tenders = AsyncMock(return_value={
        "results": [
            {"id": str(uuid4()), "winning_bid_percent_diff": -6.00, "type": "Historical"}
        ]
    })
    
    # Mock probability CDF math returns 50% for proposed bid at mean
    mock_rec_service.calculate_win_probability.return_value = 0.50
    
    # Run simulation: material +10%, labour +5%, proposed bid deviation -6.0% (at mean)
    # Materials are 60%, Labour is 40%
    # Mat factor: 0.60 * 1.10 = 0.66
    # Lab factor: 0.40 * 1.05 = 0.42
    # Combined factor = 1.08 (8% BCC cost inflation!)
    # Simulated BCC = 100,000 * 1.08 = 108,000
    # Overheads = 108,000 * 10% = 10,800
    # Taxable Base = 118,800
    # Tax = 118,800 * 5% = 5,940
    # Simulated break-even cost = 118,800 + 5,940 = 124,740.00
    # Cost increase = (124,740 - 115,500) / 115,500 * 100 = 8.0%
    # Proposed bid = 120,000 * (1 - 0.06) = 112,800.00
    # Simulated profit = 112,800.00 - 124,740.00 = -11,940.00 (Unviable)
    res = await service.run_whatif_simulation(
        mock_db_session,
        tender_id=str(tender_uuid),
        material_multiplier=10.0,
        labour_multiplier=5.0,
        proposed_bid_deviation=-6.00,
        overhead_percent=10.0,
        tax_percent=5.0
    )
    
    assert res["tender_number"] == "T-SIM-01"
    assert res["official_estimated_cost"] == 120000.00
    assert res["original_break_even"] == 115500.00
    assert res["simulated_break_even"] == 124740.00
    assert res["simulated_cost_increase_percent"] == 8.00
    
    prop_bid = res["proposed_bid"]
    assert prop_bid["amount"] == 112800.00
    assert prop_bid["simulated_profit"] == -11940.00
    assert prop_bid["win_probability_percent"] == 50.00
    assert res["viability_status"] == "Unviable (Bid Below Cost)"


@pytest.mark.asyncio
@patch("app.api.deps.user_repository")
async def test_simulations_endpoints(mock_user_repo, client) -> None:
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
    mock_sim_result = {
        "tender_id": tender_id,
        "simulated_break_even": 124740.0,
        "viability_status": "Unviable"
    }
    
    with patch.object(simulation_service, "run_whatif_simulation", AsyncMock(return_value=mock_sim_result)):
        response = await client.post(
            f"/api/v1/simulations/{tender_id}/run?material_multiplier=10.0&labour_multiplier=5.0&proposed_bid_deviation=-6.0",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["simulated_break_even"] == 124740.0
        assert data["viability_status"] == "Unviable"
