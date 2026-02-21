"""Tests for config API endpoints."""

from __future__ import annotations

from backend.api import config as config_api


class TestConfigAPI:
    def test_get_config_requires_auth(self, client):
        response = client.get("/api/v1/config")
        assert response.status_code == 401

    def test_get_config_redacts_secrets(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(config_api.settings, "api_key", "super-secret")
        monkeypatch.setattr(
            config_api.settings, "database_url", "postgresql://user:pass@localhost/db"
        )

        response = client.get("/api/v1/config", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["api_key"] == "***"
        assert data["database_url"] == "***"
        assert data["cors_origins"] == config_api.settings.cors_origins

    def test_put_config_updates_runtime_values(self, client, auth_headers, monkeypatch):
        monkeypatch.setattr(config_api.settings, "cors_origins", "http://localhost:3000")
        monkeypatch.setattr(config_api.settings, "log_level", "INFO")

        response = client.put(
            "/api/v1/config",
            headers=auth_headers,
            json={
                "cors_origins": "http://localhost:3000,http://localhost:8000",
                "log_level": "DEBUG",
                "api_key": "new-api-key",
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert data["cors_origins"] == "http://localhost:3000,http://localhost:8000"
        assert data["log_level"] == "DEBUG"
        assert data["api_key"] == "***"
