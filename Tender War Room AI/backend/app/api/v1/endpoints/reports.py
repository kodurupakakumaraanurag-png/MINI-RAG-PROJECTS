from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.services.report_service import report_service

router = APIRouter()


@router.get("/{tender_id}/print", response_class=HTMLResponse, status_code=status.HTTP_200_OK)
async def print_tender_report(
    tender_id: str,
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Generate and serve a printable HTML report dossier containing specs, custom BOQ cost sheets,
    optimal bidding strategy guidelines, and Gemini risk evaluations.
    """
    try:
        html_content = await report_service.generate_print_report(db, tender_id)
        return HTMLResponse(content=html_content, status_code=200)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate printable report: {str(e)}"
        )
