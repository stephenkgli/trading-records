"""
Tests for the import API endpoints.

Verifies:
- CSV upload (POST /api/v1/import/csv)
- Flex trigger (POST /api/v1/import/flex/trigger)
- Import logs (GET /api/v1/import/logs)

The response model for logs is ImportLogListResponse with field: logs (not items).

Reference: design-doc-final.md Section 6.1
"""

from pathlib import Path
from unittest.mock import patch, MagicMock
import uuid

import pytest

from backend.schemas.import_result import ImportResult


FIXTURES_DIR = Path(__file__).parents[1] / "fixtures"


# ===========================================================================
# CSV Upload
# ===========================================================================

class TestCSVUpload:
    """Test CSV file upload endpoint."""

    def test_upload_ibkr_csv(self, client, auth_headers, ibkr_activity_csv):
        """Uploading a valid IBKR CSV should succeed."""
        response = client.post(
            "/api/v1/import/csv",
            headers=auth_headers,
            files={"file": ("ibkr_activity.csv", ibkr_activity_csv, "text/csv")},
        )
        assert response.status_code in (200, 201)
        data = response.json()
        assert "records_imported" in data

    def test_upload_empty_csv(self, client, auth_headers):
        """Uploading an empty CSV should return 400."""
        response = client.post(
            "/api/v1/import/csv",
            headers=auth_headers,
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert response.status_code == 400

    def test_upload_requires_auth(self, client):
        """CSV upload should require authentication."""
        response = client.post(
            "/api/v1/import/csv",
            files={"file": ("test.csv", b"data", "text/csv")},
        )
        assert response.status_code == 401

    def test_upload_no_file(self, client, auth_headers):
        """Request without a file should return 422."""
        response = client.post(
            "/api/v1/import/csv",
            headers=auth_headers,
        )
        assert response.status_code == 422


# ===========================================================================
# Flex Trigger
# ===========================================================================

class TestFlexTrigger:
    """Test manual Flex Query trigger endpoint."""

    @patch("backend.api.imports.IBKRFlexIngester")
    def test_trigger_flex_query(self, mock_ingester_cls, client, auth_headers):
        """POST /api/v1/import/flex/trigger should trigger an import."""
        mock_result = ImportResult(
            import_log_id=uuid.uuid4(),
            source="flex_query",
            status="success",
            records_total=5,
            records_imported=5,
            records_skipped_dup=0,
            records_failed=0,
        )
        mock_ingester_cls.return_value.fetch_and_import.return_value = mock_result

        response = client.post("/api/v1/import/flex/trigger", headers=auth_headers)
        assert response.status_code in (200, 201, 202)

    def test_flex_trigger_requires_auth(self, client):
        """Flex trigger should require authentication."""
        response = client.post("/api/v1/import/flex/trigger")
        assert response.status_code == 401


# ===========================================================================
# Import Logs
# ===========================================================================

class TestImportLogs:
    """Test import logs endpoint."""

    def test_get_import_logs_empty(self, client, auth_headers):
        """GET /api/v1/import/logs should return empty list when no imports."""
        response = client.get("/api/v1/import/logs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert len(data["logs"]) == 0

    def test_import_logs_after_csv_upload(self, client, auth_headers, ibkr_activity_csv):
        """Import logs should include an entry after a CSV import."""
        # Upload CSV
        client.post(
            "/api/v1/import/csv",
            headers=auth_headers,
            files={"file": ("ibkr.csv", ibkr_activity_csv, "text/csv")},
        )

        # Check logs
        response = client.get("/api/v1/import/logs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) >= 1

    def test_import_logs_require_auth(self, client):
        """Import logs should require authentication."""
        response = client.get("/api/v1/import/logs")
        assert response.status_code == 401

    def test_import_log_fields(self, client, auth_headers, ibkr_activity_csv):
        """Import log entry should contain expected fields."""
        client.post(
            "/api/v1/import/csv",
            headers=auth_headers,
            files={"file": ("ibkr.csv", ibkr_activity_csv, "text/csv")},
        )

        response = client.get("/api/v1/import/logs", headers=auth_headers)
        data = response.json()

        if data["logs"]:
            log = data["logs"][0]
            expected_fields = ["id", "source", "status", "records_total", "records_imported"]
            for field in expected_fields:
                assert field in log, f"Missing field: {field}"
