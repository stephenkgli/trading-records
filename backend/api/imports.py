"""Import API endpoints — CSV upload and import logs."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from backend.api.dependencies import get_import_service
from backend.database import get_db
from backend.schemas.import_result import (
    BatchImportAggregate,
    BatchImportResponse,
    FileImportResult,
    ImportLogListResponse,
    ImportResult,
)
from backend.services.import_service import ImportService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/import", tags=["import"])


def _aggregate_batch_results(results: list[FileImportResult]) -> BatchImportAggregate:
    """Aggregate per-file import results into a batch summary."""
    files_total = len(results)
    files_success = sum(1 for item in results if item.status == "success")
    files_partial = sum(1 for item in results if item.status == "partial")
    files_failed = sum(1 for item in results if item.status == "failed")

    if files_total == 0 or files_failed == files_total:
        status = "failed"
    elif files_success == files_total:
        status = "success"
    else:
        status = "partial"

    return BatchImportAggregate(
        status=status,
        files_total=files_total,
        files_success=files_success,
        files_partial=files_partial,
        files_failed=files_failed,
        records_total=sum(item.records_total for item in results),
        records_imported=sum(item.records_imported for item in results),
        records_skipped_dup=sum(item.records_skipped_dup for item in results),
        records_failed=sum(item.records_failed for item in results),
    )


def _build_file_result(filename: str, result: ImportResult) -> FileImportResult:
    """Convert single-file import result to batch file result."""
    return FileImportResult(
        filename=filename,
        status=result.status,
        import_log_id=result.import_log_id,
        source=result.source,
        records_total=result.records_total,
        records_imported=result.records_imported,
        records_skipped_dup=result.records_skipped_dup,
        records_failed=result.records_failed,
        errors=result.errors,
    )


def _build_failed_file_result(filename: str, error_message: str) -> FileImportResult:
    """Create a failed per-file result."""
    return FileImportResult(
        filename=filename,
        status="failed",
        file_error=error_message,
    )


async def _process_single_upload(
    upload: UploadFile,
    db: Session,
    service: ImportService,
) -> FileImportResult:
    """Process one uploaded CSV and return per-file result."""
    filename = upload.filename or "unknown.csv"

    if not upload.filename:
        return _build_failed_file_result(filename, "Filename is required")

    content = await upload.read()
    if not content:
        return _build_failed_file_result(filename, "Empty file")

    try:
        result = service.import_csv(content, filename=upload.filename, db=db)
        return _build_file_result(upload.filename, result)
    except ValueError as err:
        return _build_failed_file_result(filename, str(err))
    except Exception as err:  # pragma: no cover - defensive branch
        logger.error("csv_import_error", filename=filename, error=str(err))
        return _build_failed_file_result(filename, f"Import failed: {err}")


@router.post("/csv", response_model=BatchImportResponse)
async def upload_csv(
    file: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    service: ImportService = Depends(get_import_service),
):
    """Upload one or more CSV files for import.

    The same endpoint supports single-file and multi-file uploads.
    Each file is processed independently; file-level failures do not stop
    the rest of the batch.
    """
    if not file:
        raise HTTPException(status_code=400, detail="At least one file is required")

    file_results = [
        await _process_single_upload(upload=item, db=db, service=service)
        for item in file
    ]

    return BatchImportResponse(
        aggregate=_aggregate_batch_results(file_results),
        files=file_results,
    )


@router.get("/logs", response_model=ImportLogListResponse)
def list_import_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    service: ImportService = Depends(get_import_service),
):
    """List import history."""
    return service.list_import_logs(db, page=page, per_page=per_page)
