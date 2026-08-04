from typing import Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from celery.result import AsyncResult

from app.api import deps
from app.models.user import User, UserRole
from app.models.tender import Tender
from app.repositories.tender_repo import tender_repository
from app.workers.celery_app import celery_app

router = APIRouter()


@router.post("/scrape", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scraper(
    *,
    db: AsyncSession = Depends(deps.get_db),
    query: str = "SCCL",
    current_user: User = Depends(deps.RoleChecker([UserRole.ADMIN, UserRole.ANALYST]))
) -> Any:
    """
    Manually queue the Playwright scraper Celery task in the background.
    """
    from app.workers.tasks import run_scraper_task
    task = run_scraper_task.delay(query)
    return {
        "message": "Scraper task has been queued successfully",
        "task_id": task.id,
        "status": task.status
    }


@router.get("/scrape/status/{task_id}")
async def get_scraper_status(
    task_id: str,
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Check the status of a queued scraper task.
    """
    result = AsyncResult(task_id, app=celery_app)
    response = {
        "task_id": task_id,
        "status": result.status,
    }
    if result.status == "SUCCESS":
        response["result"] = result.result
    elif result.status == "FAILURE":
        response["error"] = str(result.info)
    return response


@router.post("/{id}/extract", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pdf_extraction(
    id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.RoleChecker([UserRole.ADMIN, UserRole.ANALYST]))
) -> Any:
    """
    Queue background task to extract metadata from downloaded tender PDF.
    """
    tender = await tender_repository.get(db, id)
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found"
        )
    
    from app.workers.tasks import run_extraction_task
    task = run_extraction_task.delay(str(id))
    return {
        "message": "PDF extraction task has been queued successfully",
        "task_id": task.id,
        "status": task.status
    }


@router.post("/search/similar")
async def search_similar_tenders(
    *,
    query: str,
    limit: int = 5,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Search similar historical and current tenders based on work scope.
    """
    from app.services.similarity_service import similarity_service
    results = await similarity_service.search_similar_tenders(db, query_text=query, limit=limit)
    return results


@router.get("/", response_model=List[dict])


async def list_tenders(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Retrieve tender listings.
    """
    tenders = await tender_repository.list_tenders(db, skip=skip, limit=limit)
    # Serialize output dictionary list manually or define Pydantic schema
    return [
        {
            "id": str(t.id),
            "tender_number": t.tender_number,
            "work_name": t.work_name,
            "estimated_cost": float(t.estimated_cost) if t.estimated_cost else None,
            "emd": float(t.emd) if t.emd else None,
            "closing_date": t.closing_date.isoformat() if t.closing_date else None,
            "status": t.status.value,
            "created_at": t.created_at.isoformat() if t.created_at else None
        }
        for t in tenders
    ]


@router.get("/{id}")
async def get_tender_detail(
    id: UUID,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Retrieve detailed view of a single tender along with its versioned documents.
    """
    tender = await tender_repository.get(db, id)
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender not found"
        )
        
    # Get related documents
    from sqlalchemy import select
    from app.models.tender import TenderDocument
    result = await db.execute(
        select(TenderDocument).filter(
            TenderDocument.tender_id == tender.id
        )
    )
    docs = result.scalars().all()
    
    return {
        "id": str(tender.id),
        "tender_number": tender.tender_number,
        "work_name": tender.work_name,
        "estimated_cost": float(tender.estimated_cost) if tender.estimated_cost else None,
        "emd": float(tender.emd) if tender.emd else None,
        "status": tender.status.value,
        "closing_date": tender.closing_date.isoformat() if tender.closing_date else None,
        "documents": [
            {
                "id": str(d.id),
                "document_type": d.document_type,
                "file_name": d.file_name,
                "file_path": d.file_path,
                "file_hash": d.file_hash,
                "version": d.version,
                "is_active": d.is_active,
                "downloaded_at": d.downloaded_at.isoformat()
            }
            for d in docs
        ]
    }
