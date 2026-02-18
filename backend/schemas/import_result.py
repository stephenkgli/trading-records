"""Import result schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


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


class ImportResult(BaseModel):
    """Result returned after an import operation."""

    import_log_id: uuid.UUID
    source: str
    status: str
    records_total: int
    records_imported: int
    records_skipped_dup: int
    records_failed: int
    errors: list[dict] = []


class ImportLogListResponse(BaseModel):
    """Paginated list of import logs."""

    logs: list[ImportLogResponse]
    total: int
    page: int
    per_page: int
