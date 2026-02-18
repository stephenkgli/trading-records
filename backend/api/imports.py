"""Import API endpoints — CSV upload, Flex trigger, import logs."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.ingestion.csv_importer import CSVImporter
from backend.ingestion.ibkr_flex import IBKRFlexIngester
from backend.models.import_log import ImportLog
from backend.schemas.import_result import (
    ImportLogListResponse,
    ImportLogResponse,
    ImportResult,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/import", tags=["import"])


@router.post("/csv", response_model=ImportResult)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a CSV file for import.

    Automatically detects IBKR or Tradovate format.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    logger.info("csv_upload", filename=file.filename, size=len(content))

    try:
        importer = CSVImporter()
        result = importer.import_csv(content, filename=file.filename, db=db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("csv_import_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/flex/trigger", response_model=ImportResult)
def trigger_flex_query(db: Session = Depends(get_db)):
    """Manually trigger an IBKR Flex Query import."""
    try:
        ingester = IBKRFlexIngester()
        result = ingester.fetch_and_import(db=db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("flex_trigger_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Flex Query import failed: {str(e)}")


@router.post("/tradovate/trigger", response_model=ImportResult)
def trigger_tradovate(db: Session = Depends(get_db)):
    """Manually trigger a Tradovate API import."""
    try:
        from backend.ingestion.tradovate import TradovateIngester

        ingester = TradovateIngester()
        result = ingester.fetch_and_import(db=db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("tradovate_trigger_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Tradovate import failed: {str(e)}")


@router.get("/logs", response_model=ImportLogListResponse)
def list_import_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List import history."""
    count_query = select(func.count()).select_from(ImportLog)
    total = db.execute(count_query).scalar_one()

    query = (
        select(ImportLog)
        .order_by(ImportLog.started_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    logs = db.execute(query).scalars().all()

    return ImportLogListResponse(
        logs=[ImportLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        per_page=per_page,
    )
