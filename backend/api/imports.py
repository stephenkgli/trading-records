"""Import API endpoints — CSV upload and import logs."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from backend.api.dependencies import get_import_service
from backend.database import get_db
from backend.schemas.import_result import (
    ImportLogListResponse,
    ImportResult,
)
from backend.services.import_service import ImportService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/import", tags=["import"])


@router.post("/csv", response_model=ImportResult)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    service: ImportService = Depends(get_import_service),
):
    """Upload a CSV file for import.

    Automatically detects IBKR or Tradovate format.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    try:
        return service.import_csv(content, filename=file.filename, db=db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("csv_import_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.get("/logs", response_model=ImportLogListResponse)
def list_import_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    service: ImportService = Depends(get_import_service),
):
    """List import history."""
    return service.list_import_logs(db, page=page, per_page=per_page)
