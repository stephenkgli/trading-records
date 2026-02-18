"""
Tests for API key authentication middleware.

Verifies:
- No API key -> 401
- Wrong API key -> 401
- Correct API key -> 200
- API_KEY not set -> all requests pass (dev mode)

The auth middleware reads `backend.config.settings.api_key` directly.
In tests, we patch it via conftest.py client fixtures.

Reference: design-doc-final.md Section 6.3
"""

import pytest


class TestAuthWithKeyRequired:
    """Test auth behavior when API_KEY is configured (via 'client' fixture)."""

    def test_no_key_returns_401(self, client):
        """Request without X-API-Key header should return 401."""
        response = client.get("/api/v1/trades")
        assert response.status_code == 401

    def test_wrong_key_returns_401(self, client, bad_auth_headers):
        """Request with incorrect API key should return 401."""
        response = client.get("/api/v1/trades", headers=bad_auth_headers)
        assert response.status_code == 401

    def test_correct_key_passes(self, client, auth_headers):
        """Request with correct API key should pass authentication."""
        response = client.get("/api/v1/trades", headers=auth_headers)
        # Should not be 401 (might be 200 with empty data)
        assert response.status_code != 401

    def test_401_response_body(self, client):
        """401 response should include an error detail message."""
        response = client.get("/api/v1/trades")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_health_bypass_auth(self, client):
        """/health should bypass auth even when API_KEY is set."""
        response = client.get("/health")
        assert response.status_code == 200


class TestAuthWithKeyDisabled:
    """Test auth behavior when API_KEY is empty (via 'client_no_auth' fixture)."""

    def test_no_key_set_allows_all(self, client_no_auth):
        """When API_KEY is empty, all /api requests should pass."""
        response = client_no_auth.get("/api/v1/trades")
        assert response.status_code != 401

    def test_no_key_set_with_header(self, client_no_auth):
        """Even with a random X-API-Key header, should pass when API_KEY is empty."""
        response = client_no_auth.get(
            "/api/v1/trades",
            headers={"X-API-Key": "anything"}
        )
        assert response.status_code != 401

    def test_no_key_set_import_endpoint(self, client_no_auth):
        """Import endpoints should also be accessible when API_KEY is empty."""
        response = client_no_auth.get("/api/v1/import/logs")
        assert response.status_code != 401
