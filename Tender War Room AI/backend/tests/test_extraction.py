from unittest.mock import patch, AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone
import pytest
from fastapi import status

from app.models.user import User, UserRole
from app.models.tender import Tender, TenderDocument, TenderStatus
from app.services.extraction_service import PDFExtractionService, pdf_extraction_service
from app.core import security


def test_clean_numeric() -> None:
    service = PDFExtractionService()
    assert service.clean_numeric("Rs. 54,00,000.00") == 5400000.00
    assert service.clean_numeric("1,250") == 1250.0
    assert service.clean_numeric("N/A") is None


def test_clean_integer() -> None:
    service = PDFExtractionService()
    assert service.clean_integer("12 months") == 12
    assert service.clean_integer("6") == 6
    assert service.clean_integer("None") is None


def test_parse_metadata_with_regex() -> None:
    service = PDFExtractionService()
    sample_text = (
        "GOVERNMENT OF TELANGANA\n"
        "Tender Notice No: TS-SCCL-2026-99A\n"
        "Estimated Contract Value: Rs. 4,50,00,000.00\n"
        "Earnest Money Deposit (EMD): Rs. 4,50,000.00\n"
        "Period of Completion: 18 months\n"
        "Registration Class of Contractor: Class I Class Contractors\n"
    )
    
    metadata = service.parse_metadata_with_regex(sample_text)
    
    assert metadata["tender_number"] == "TS-SCCL-2026-99A"
    assert metadata["estimated_cost"] == 45000000.00
    assert metadata["emd"] == 450000.00
    assert metadata["completion_period_months"] == 18
    assert metadata["bidding_class"] == "I"


@pytest.mark.asyncio
@patch("app.api.deps.user_repository")
async def test_trigger_pdf_extraction_endpoint(mock_user_repo, client, mock_db_session) -> None:
    """
    Test manual trigger endpoint queues the Celery extraction task.
    """
    admin_uuid = uuid4()
    mock_admin = User(
        id=admin_uuid,
        username="admin",
        email="admin@example.com",
        role=UserRole.ADMIN,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    mock_user_repo.get = AsyncMock(return_value=mock_admin)
    token = security.create_access_token(subject=admin_uuid)
    
    tender_id = uuid4()
    mock_tender = Tender(
        id=tender_id,
        tender_number="T-100",
        work_name="Some heavy civil construction",
        status=TenderStatus.SCRAPED
    )
    
    # Mock tender repository get call
    with patch("app.repositories.tender_repo.tender_repository.get", AsyncMock(return_value=mock_tender)):
        with patch("app.workers.tasks.run_extraction_task.delay") as mock_delay:
            mock_task = MagicMock()
            mock_task.id = "extraction-task-abc"
            mock_task.status = "PENDING"
            mock_delay.return_value = mock_task
            
            response = await client.post(
                f"/api/v1/tenders/{tender_id}/extract",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            data = response.json()
            assert data["task_id"] == "extraction-task-abc"
            assert data["status"] == "PENDING"
            mock_delay.assert_called_once_with(str(tender_id))


@pytest.mark.asyncio
@patch("app.repositories.tender_repo.tender_repository.get")
async def test_extract_and_update_tender_service_flow(mock_get_tender, mock_db_session) -> None:
    """
    Verifies extraction flow successfully fetches doc, parses text, and updates Tender record.
    """
    tender_id = uuid4()
    mock_tender = Tender(
        id=tender_id,
        tender_number="DUMMY-TENDER",
        work_name="Civil road repairs",
        status=TenderStatus.SCRAPED
    )
    mock_get_tender.return_value = mock_tender
    
    # Mock document fetch: return dummy notice doc
    mock_doc = TenderDocument(
        tender_id=tender_id,
        document_type="TenderNotice",
        file_name="notice.pdf",
        file_path="C:/dummy/notice.pdf",
        file_hash="xyz",
        is_active=True
    )
    
    # Mock db session execute for select(TenderDocument)
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_doc
    mock_db_session.execute.return_value = mock_result
    
    dummy_text = (
        "Tender Notice No: TS-ROAD-555\n"
        "Estimated Contract Value: Rs. 9,99,999.00\n"
        "Earnest Money Deposit (EMD): Rs. 9,999.00\n"
        "Period of Completion: 6 months\n"
    )
    
    # Mock physical file exist check and PDF reading
    with patch("app.services.extraction_service.Path.exists", return_value=True):
        with patch.object(pdf_extraction_service, "extract_text_from_pdf", return_value=dummy_text):
            # We mock Gemini call to return empty dict to test regex parser integration fallback
            with patch.object(pdf_extraction_service, "parse_metadata_with_llm", AsyncMock(return_value={})):
                updated_tender = await pdf_extraction_service.extract_and_update_tender(mock_db_session, str(tender_id))
                
                assert updated_tender.tender_number == "TS-ROAD-555"
                assert float(updated_tender.estimated_cost) == 999999.00
                assert float(updated_tender.emd) == 9999.00
                assert updated_tender.completion_period_months == 6
                assert updated_tender.status == TenderStatus.EXTRACTED
