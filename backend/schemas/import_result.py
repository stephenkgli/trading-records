"""Import result schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ImportLogResponse(BaseModel):
    """Import log entry in API response."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    source: str
    status: str
    records_total: int
    records_imported: int
    records_skipped_dup: int
    records_failed: int
    errors: dict | None = None
    started_at: datetime
    completed_at: datetime | None = None
    trade_date_from: datetime | None = None
    trade_date_to: datetime | None = None
    broker: str | None = None


class ImportResult(BaseModel):
    """Result returned after an import operation."""

    import_log_id: uuid.UUID
    source: str
    status: str
    records_total: int
    records_imported: int
    records_skipped_dup: int
    records_failed: int
    errors: list[dict] = Field(default_factory=list)


class FileImportResult(BaseModel):
    """Per-file result in batch import response."""

    filename: str
    status: str
    import_log_id: uuid.UUID | None = None
    source: str = "csv"
    records_total: int = 0
    records_imported: int = 0
    records_skipped_dup: int = 0
    records_failed: int = 0
    errors: list[dict] = Field(default_factory=list)
    file_error: str | None = None


class BatchImportAggregate(BaseModel):
    """Aggregated counters for a batch import."""

    status: str
    files_total: int
    files_success: int
    files_partial: int
    files_failed: int
    records_total: int
    records_imported: int
    records_skipped_dup: int
    records_failed: int


class BatchImportResponse(BaseModel):
    """Response returned after importing multiple CSV files."""

    aggregate: BatchImportAggregate
    files: list[FileImportResult]


class ImportLogListResponse(BaseModel):
    """Paginated list of import logs."""

    logs: list[ImportLogResponse]
    total: int
    page: int
    per_page: int
