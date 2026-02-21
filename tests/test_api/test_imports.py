"""
Tests for the import API endpoints.

Verifies:
- CSV upload (POST /api/v1/import/csv)
- Import logs (GET /api/v1/import/logs)

The response model for logs is ImportLogListResponse with field: logs (not items).

Reference: design-doc-final.md Section 6.1
"""

# ===========================================================================
# CSV Upload
# ===========================================================================

class TestCSVUpload:
    """Test CSV file upload endpoint."""

    def test_upload_ibkr_csv(self, client, ibkr_activity_csv):
        """Uploading a valid IBKR CSV should succeed."""
        response = client.post(
            "/api/v1/import/csv",
            files={"file": ("ibkr_activity.csv", ibkr_activity_csv, "text/csv")},
        )
        assert response.status_code in (200, 201)
        data = response.json()
        assert "records_imported" in data

    def test_upload_tradovate_performance_csv(
        self,
        client,
        
        tradovate_performance_csv,
        tradovate_expected_trade_count,
    ):
        """Uploading Tradovate Performance CSV should succeed with full count."""
        response = client.post(
            "/api/v1/import/csv",
            files={"file": ("Performance.csv", tradovate_performance_csv, "text/csv")},
        )
        assert response.status_code in (200, 201)
        data = response.json()
        assert data["records_total"] == tradovate_expected_trade_count
        assert data["records_imported"] == tradovate_expected_trade_count

    def test_upload_empty_csv(self, client):
        """Uploading an empty CSV should return 400."""
        response = client.post(
            "/api/v1/import/csv",
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert response.status_code == 400

    def test_upload_no_file(self, client):
        """Request without a file should return 422."""
        response = client.post(
            "/api/v1/import/csv",
        )
        assert response.status_code == 422


# ===========================================================================
# Import Logs
# ===========================================================================

class TestImportLogs:
    """Test import logs endpoint."""

    def test_get_import_logs_empty(self, client):
        """GET /api/v1/import/logs should return empty list when no imports."""
        response = client.get("/api/v1/import/logs")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert len(data["logs"]) == 0

    def test_import_logs_after_csv_upload(self, client, ibkr_activity_csv):
        """Import logs should include an entry after a CSV import."""
        # Upload CSV
        client.post(
            "/api/v1/import/csv",
            files={"file": ("ibkr.csv", ibkr_activity_csv, "text/csv")},
        )

        # Check logs
        response = client.get("/api/v1/import/logs")
        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) >= 1

    def test_import_log_fields(self, client, ibkr_activity_csv):
        """Import log entry should contain expected fields."""
        client.post(
            "/api/v1/import/csv",
            files={"file": ("ibkr.csv", ibkr_activity_csv, "text/csv")},
        )

        response = client.get("/api/v1/import/logs")
        data = response.json()

        if data["logs"]:
            log = data["logs"][0]
            expected_fields = ["id", "source", "status", "records_total", "records_imported"]
            for field in expected_fields:
                assert field in log, f"Missing field: {field}"
