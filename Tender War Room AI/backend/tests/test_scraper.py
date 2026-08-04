import os
import pytest
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi import status

from app.models.user import User, UserRole
from app.models.tender import Tender, TenderDocument, TenderStatus
from app.services.scraper_service import TenderScraperService
from app.core import security


@pytest.fixture
def temp_storage(tmp_path) -> Path:
    return tmp_path


@pytest.mark.asyncio
async def test_save_and_hash_file_new_document(temp_storage, mock_db_session) -> None:
    """
    Test saving a document for the first time creates a Version 1 document.
    """
    service = TenderScraperService(storage_dir=str(temp_storage))
    
    # Create dummy temp download file
    temp_file = temp_storage / "temp_doc.pdf"
    with open(temp_file, "w") as f:
        f.write("Tender scope description document content")
        
    tender_uuid = uuid4()
    
    # Mock repository checks: returns None (no active doc with this name exists)
    file_hash = service.calculate_file_hash(temp_file)
    
    with patch("app.repositories.tender_repo.tender_repository.get_active_document_by_name", AsyncMock(return_value=None)):
        mock_doc = TenderDocument(
            tender_id=tender_uuid,
            document_type="TenderNotice",
            file_name="notice.pdf",
            file_path=str(temp_storage / str(tender_uuid) / "notice.pdf"),
            file_hash=file_hash,
            version=1,
            is_active=True,
            downloaded_at=datetime.now(timezone.utc)
        )
        
        with patch("app.repositories.tender_repo.tender_repository.add_document", AsyncMock(return_value=mock_doc)):
            path, returned_hash, version = await service.save_and_hash_file(
                mock_db_session,
                tender_id=tender_uuid,
                temp_file_path=temp_file,
                file_name="notice.pdf",
                document_type="TenderNotice"
            )
            
            assert version == 1
            assert returned_hash == file_hash



@pytest.mark.asyncio
async def test_save_and_hash_file_duplicate_document(temp_storage, mock_db_session) -> None:
    """
    Test downloading a document with identical hash does not save a duplicate.
    """
    service = TenderScraperService(storage_dir=str(temp_storage))
    
    # Create file
    temp_file = temp_storage / "temp_doc.pdf"
    with open(temp_file, "w") as f:
        f.write("Same content")
    file_hash = service.calculate_file_hash(temp_file)
        
    tender_uuid = uuid4()
    
    # Mock existing active doc in database with identical hash
    existing_doc = TenderDocument(
        tender_id=tender_uuid,
        document_type="TenderNotice",
        file_name="notice.pdf",
        file_path=str(temp_storage / str(tender_uuid) / "notice.pdf"),
        file_hash=file_hash,
        version=1,
        is_active=True,
        downloaded_at=datetime.now(timezone.utc)
    )
    
    with patch("app.repositories.tender_repo.tender_repository.get_active_document_by_name", AsyncMock(return_value=existing_doc)):
        path, returned_hash, version = await service.save_and_hash_file(
            mock_db_session,
            tender_id=tender_uuid,
            temp_file_path=temp_file,
            file_name="notice.pdf",
            document_type="TenderNotice"
        )
        # Should return existing record without calling add_document
        assert version == 1
        assert returned_hash == file_hash
        assert not temp_file.exists() # temp file was cleaned up


@pytest.mark.asyncio
async def test_save_and_hash_file_updated_document(temp_storage, mock_db_session) -> None:
    """
    Test downloading an updated document with different hash increments version.
    """
    service = TenderScraperService(storage_dir=str(temp_storage))
    
    temp_file = temp_storage / "temp_doc.pdf"
    with open(temp_file, "w") as f:
        f.write("New updated content")
    new_hash = service.calculate_file_hash(temp_file)
        
    tender_uuid = uuid4()
    
    existing_doc = TenderDocument(
        tender_id=tender_uuid,
        document_type="TenderNotice",
        file_name="notice.pdf",
        file_path=str(temp_storage / str(tender_uuid) / "notice.pdf"),
        file_hash="old_hash_123",
        version=1,
        is_active=True,
        downloaded_at=datetime.now(timezone.utc)
    )
    
    mock_new_doc = TenderDocument(
        tender_id=tender_uuid,
        document_type="TenderNotice",
        file_name="notice.pdf",
        file_path=str(temp_storage / str(tender_uuid) / "notice.pdf"),
        file_hash=new_hash,
        version=2,
        is_active=True,
        downloaded_at=datetime.now(timezone.utc)
    )
    
    with patch("app.repositories.tender_repo.tender_repository.get_active_document_by_name", AsyncMock(return_value=existing_doc)):
        with patch("app.repositories.tender_repo.tender_repository.add_document", AsyncMock(return_value=mock_new_doc)):
            path, returned_hash, version = await service.save_and_hash_file(
                mock_db_session,
                tender_id=tender_uuid,
                temp_file_path=temp_file,
                file_name="notice.pdf",
                document_type="TenderNotice"
            )
            assert version == 2
            assert returned_hash == new_hash


@pytest.mark.asyncio
@patch("app.api.deps.user_repository")
async def test_trigger_scraper_endpoint(mock_user_repo, client) -> None:
    """
    Test trigger endpoint launches background Celery task.
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
    
    # Mock celery task .delay trigger
    with patch("app.workers.tasks.run_scraper_task.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "task-id-123"
        mock_task.status = "PENDING"
        mock_delay.return_value = mock_task
        
        response = await client.post(
            "/api/v1/tenders/scrape?query=SCCL",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["task_id"] == "task-id-123"
        assert data["status"] == "PENDING"
        mock_delay.assert_called_once_with("SCCL")


@pytest.mark.asyncio
@patch("app.api.deps.user_repository")
@patch("app.repositories.tender_repo.tender_repository.list_tenders")
async def test_list_tenders(mock_list, mock_user_repo, client) -> None:
    """
    Test list tenders endpoint formats rows.
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
    
    # Mock repositories return list
    mock_tender = Tender(
        id=uuid4(),
        tender_number="T-1",
        work_name="Build road",
        estimated_cost=100000.0,
        emd=1000.0,
        closing_date=datetime.now(timezone.utc),
        status=TenderStatus.SCRAPED,
        created_at=datetime.now(timezone.utc)
    )
    mock_list.return_value = [mock_tender]
    
    response = await client.get(
        "/api/v1/tenders/",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    assert data[0]["tender_number"] == "T-1"
    assert data[0]["work_name"] == "Build road"
