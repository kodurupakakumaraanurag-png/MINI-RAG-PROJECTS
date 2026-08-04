from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4, UUID
from datetime import datetime, timezone
import pytest
from fastapi import status

from app.models.user import User, UserRole
from app.models.tender import Tender, TenderStatus
from app.models.recommendation import BidRecommendation
from app.services.recommendation_service import RecommendationService, recommendation_service
from app.core import security


def test_win_probability_cdf_math() -> None:
    service = RecommendationService()
    mean = -6.0
    std = 2.0
    
    # 1. Bidding exactly at the historical mean should give exactly 50% probability
    prob_mean = service.calculate_win_probability(-6.0, mean, std)
    assert pytest.approx(prob_mean, 0.01) == 0.50
    
    # 2. Bidding lower (more competitive, e.g. -8.0) should give higher probability (>50%)
    prob_low = service.calculate_win_probability(-8.0, mean, std)
    assert prob_low > 0.50
    
    # 3. Bidding higher (less competitive, e.g. -4.0) should give lower probability (<50%)
    prob_high = service.calculate_win_probability(-4.0, mean, std)
    assert prob_high < 0.50


@pytest.mark.asyncio
@patch("app.services.recommendation_service.estimation_service")
@patch("app.services.recommendation_service.similarity_service")
async def test_generate_recommendation_flow(mock_similarity, mock_estimation, mock_db_session) -> None:
    service = RecommendationService()
    tender_uuid = uuid4()
    
    # 1. Mock tender
    mock_tender = Tender(
        id=tender_uuid,
        tender_number="T-REC-01",
        work_name="Pipeline expansion under SCCL",
        eligibility_criteria="Class I contractor required",
        penalty_clauses="0.5% penalty per week delay"
    )
    mock_db_session.get.return_value = mock_tender
    
    # 2. Mock contractor cost summary (break-even is 90,000, official estimate is 100,000)
    # Break-even deviation = -10.00%
    mock_estimation.get_cost_sheet_summary = AsyncMock(return_value={
        "official_estimated_cost": 100000.00,
        "break_even_cost": 90000.00
    })
    
    # 3. Mock similarity search (similar bids are: -4.0%, -6.0%, -8.0% -> mean is -6.0%)
    mock_similarity.search_similar_tenders = AsyncMock(return_value={
        "results": [
            {"id": str(uuid4()), "winning_bid_percent_diff": -4.00, "type": "Historical"},
            {"id": str(uuid4()), "winning_bid_percent_diff": -6.00, "type": "Historical"},
            {"id": str(uuid4()), "winning_bid_percent_diff": -8.00, "type": "Historical"}
        ]
    })
    # Mock database exists check (none exists)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = None
    mock_db_session.execute.return_value = mock_result

    
    # Run recommendation service
    rec = await service.generate_recommendation(mock_db_session, str(tender_uuid))
    
    assert rec["tender_number"] == "T-REC-01"
    assert rec["break_even_deviation_percent"] == -10.00
    
    # Recommended bid range
    rec_range = rec["recommended_bid_range"]
    assert rec_range["min_percent"] >= -10.00 # Minimum bid cannot go below break-even deviation
    assert rec_range["max_percent"] <= -4.00 # Max bid capped to keep win probability viable
    
    assert rec_range["min_profit"] >= 0.0
    assert rec_range["max_profit"] > 0.0
    
    assert rec_range["win_probability_at_min"] > 0.0
    assert rec_range["win_probability_at_max"] > 0.0


@pytest.mark.asyncio
@patch("app.api.deps.user_repository")
async def test_recommendations_endpoints(mock_user_repo, client, mock_db_session) -> None:
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
    mock_rec = {
        "id": str(uuid4()),
        "tender_id": tender_id,
        "recommended_bid_range": {"min_percent": -8.0, "max_percent": -5.0}
    }
    
    with patch.object(recommendation_service, "generate_recommendation", AsyncMock(return_value=mock_rec)):
        # Mock recommendation exist query for GET endpoint
        mock_db_rec = BidRecommendation(
            tender_id=UUID(tender_id),
            recommended_bid_range_min=-8.0,
            recommended_bid_range_max=-5.0,
            estimated_profit_min=10000.0,
            estimated_profit_max=20000.0,
            risk_score=4.0,
            confidence_level="High",
            similar_tenders_used=[],
            assumptions={}
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_db_rec
        mock_db_session.execute.return_value = mock_result
        
        # 1. Generate Recommendation (POST)
        response = await client.post(
            f"/api/v1/recommendations/{tender_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["tender_id"] == tender_id
        
        # 2. Fetch Recommendation (GET)
        response = await client.get(
            f"/api/v1/recommendations/{tender_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["recommended_bid_range"]["min_percent"] == -8.0

