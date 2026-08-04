from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
import pytest
from fastapi import status

from app.models.user import User, UserRole
from app.models.tender import Tender, Department, Area, TenderStatus
from app.models.historical import HistoricalTender
from app.services.similarity_service import SimilarityService, similarity_service
from app.core import security


@pytest.mark.asyncio
async def test_rebuild_index_and_search_logic(mock_db_session) -> None:
    """
    Test vector indexing and semantic search on simulated tenders database.
    """
    service = SimilarityService()
    
    # Create mock database entries
    hist_tender1 = HistoricalTender(
        id=uuid4(),
        tender_number="HIST-1",
        work_name="Laying of concrete pipeline at mine area",
        estimated_cost=500000.00,
        winning_bid_amount=480000.00,
        winning_bid_percent_diff=-4.00,
        completion_period_months=6
    )
    
    hist_tender2 = HistoricalTender(
        id=uuid4(),
        tender_number="HIST-2",
        work_name="Installation of heavy electrical transmission lines",
        estimated_cost=2000000.00,
        winning_bid_amount=2100000.00,
        winning_bid_percent_diff=5.00,
        completion_period_months=12
    )
    
    # Mock db session results
    mock_result_hist = MagicMock()
    mock_result_hist.scalars.return_value.all.return_value = [hist_tender1, hist_tender2]
    
    mock_result_curr = MagicMock()
    mock_result_curr.scalars.return_value.all.return_value = []
    
    mock_db_session.execute.side_effect = [mock_result_hist, mock_result_curr]
    
    # Run rebuild
    await service.rebuild_index(mock_db_session)
    
    assert service.index is not None
    assert len(service.tenders_map) == 2
    
    # Test semantic search query
    search_res = await service.search_similar_tenders(
        mock_db_session,
        query_text="mine pipeline layout",
        limit=1
    )
    
    # Check that search matches hist_tender1 due to semantic relation (pipeline/mine)
    assert len(search_res["results"]) == 1
    best_match = search_res["results"][0]
    assert best_match["tender_number"] == "HIST-1"
    assert best_match["similarity_score"] > 0.3 # cosine score should be positive
    
    # Check analytics
    assert search_res["analytics"]["avg_estimated_cost"] == 500000.00
    assert search_res["analytics"]["avg_completion_period"] == 6.00
    assert search_res["analytics"]["avg_winning_deviation_percent"] == -4.00


@pytest.mark.asyncio
@patch("app.api.deps.user_repository")
async def test_search_similar_endpoint(mock_user_repo, client, mock_db_session) -> None:
    """
    Test semantic similarity HTTP POST endpoint routing and serialization.
    """
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
    
    mock_response_data = {
        "query": "pipeline roads",
        "results": [
            {
                "id": str(uuid4()),
                "tender_number": "HIST-1",
                "work_name": "Laying roads",
                "estimated_cost": 100000.00,
                "winning_bid_amount": 95000.00,
                "winning_bid_percent_diff": -5.00,
                "completion_period_months": 3,
                "type": "Historical",
                "similarity_score": 0.85
            }
        ],
        "analytics": {
            "avg_estimated_cost": 100000.00,
            "avg_completion_period": 3.0,
            "avg_winning_deviation_percent": -5.0
        }
    }
    
    with patch.object(similarity_service, "search_similar_tenders", AsyncMock(return_value=mock_response_data)):
        response = await client.post(
            "/api/v1/tenders/search/similar?query=pipeline%20roads&limit=5",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["query"] == "pipeline roads"
        assert len(data["results"]) == 1
        assert data["results"][0]["tender_number"] == "HIST-1"
        assert data["analytics"]["avg_estimated_cost"] == 100000.00
