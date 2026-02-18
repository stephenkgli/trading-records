"""Tests for config API endpoints."""

from __future__ import annotations

from backend.api import config as config_api


class TestConfigAPI:
    def test_get_config_requires_auth(self, client):
        response = client.get("/api/v1/config")
        assert response.status_code == 401

    def test_get_config_redacts_secrets(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(config_api.settings, "api_key", "super-secret")
        monkeypatch.setattr(config_api.settings, "ibkr_flex_token", "ibkr-token")
        monkeypatch.setattr(config_api.settings, "tradovate_password", "tv-pass")

        response = client.get("/api/v1/config", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["api_key"] == "***"
        assert data["database_url"] == "***"
        assert data["ibkr"]["flex_token"] == "***"
        assert data["tradovate"]["password"] == "***"

    def test_put_config_updates_runtime_values(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(config_api.settings, "cors_origins", "http://localhost:3000")
        monkeypatch.setattr(config_api.settings, "tradovate_environment", "demo")

        response = client.put(
            "/api/v1/config",
            headers=auth_headers,
            json={
                "cors_origins": "http://localhost:3000,http://localhost:8000",
                "tradovate_environment": "live",
                "api_key": "new-api-key",
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["cors_origins"] == "http://localhost:3000,http://localhost:8000"
        assert data["tradovate"]["environment"] == "live"
        assert data["api_key"] == "***"
