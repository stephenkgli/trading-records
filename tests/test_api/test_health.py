"""
Tests for the /health endpoint.

Verifies:
- /health returns 200 without authentication
- Response includes basic health information

Reference: design-doc-final.md Section 6.1, 6.3
"""

import pytest


class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_returns_200(self, client):
        """GET /health should return 200 without any authentication."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_no_auth_required(self, client):
        """GET /health should work without X-API-Key header."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_body(self, client):
        """Health response should contain status information."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data

    def test_health_returns_503_when_db_unavailable(self, client, db_session, monkeypatch):
        """When database is unavailable, health endpoint should return 503."""

        def _raise_db_error(*args, **kwargs):
            raise RuntimeError("database unavailable")

        monkeypatch.setattr(db_session, "execute", _raise_db_error)

        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"

    def test_health_with_auth_also_works(self, client):
        """GET /health should also work if auth headers are provided."""
        response = client.get("/health")
        assert response.status_code == 200
