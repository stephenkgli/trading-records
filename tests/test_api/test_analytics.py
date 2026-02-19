"""
Tests for the analytics API endpoints.

Verifies the 5 analytics endpoints:
1. GET /api/v1/analytics/daily — daily P&L summary
2. GET /api/v1/analytics/calendar — monthly calendar data (requires year, month params)
3. GET /api/v1/analytics/by-symbol — per-symbol breakdown
4. GET /api/v1/analytics/by-strategy — per-strategy-tag breakdown
5. GET /api/v1/analytics/performance — win rate, expectancy, etc.

Reference: design-doc-final.md Section 6.1
"""


import pytest


# ===========================================================================
# 1. Daily P&L Summary
# ===========================================================================

class TestAnalyticsDaily:
    """Test GET /api/v1/analytics/daily endpoint."""

    def test_daily_returns_200(self, client, auth_headers, db_session, seed_analytics_data):
        """Daily analytics endpoint should return 200."""
        seed_analytics_data()
        response = client.get("/api/v1/analytics/daily", headers=auth_headers)
        assert response.status_code == 200

    def test_daily_with_date_range(self, client, auth_headers, db_session, seed_analytics_data):
        """Should filter by date range."""
        seed_analytics_data()
        response = client.get(
            "/api/v1/analytics/daily?from=2025-01-15&to=2025-01-16",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_daily_returns_expected_values(self, client, auth_headers, db_session, seed_analytics_data):
        """Daily summaries should fall back to trades in SQLite and compute P&L."""
        seed_analytics_data()
        response = client.get("/api/v1/analytics/daily", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert len(data) == 2
        assert data[0]["date"] == "2025-01-15"
        assert float(data[0]["net_pnl"]) == pytest.approx(498)
        assert float(data[0]["commissions"]) == pytest.approx(2)
        assert data[0]["trade_count"] == 2

        assert data[1]["date"] == "2025-01-16"
        assert float(data[1]["net_pnl"]) == pytest.approx(-252)
        assert float(data[1]["commissions"]) == pytest.approx(2)
        assert data[1]["trade_count"] == 2

    def test_daily_empty_db(self, client, auth_headers):
        """Empty database should return empty results, not error."""
        response = client.get("/api/v1/analytics/daily", headers=auth_headers)
        assert response.status_code == 200

    def test_daily_requires_auth(self, client):
        """Analytics endpoints require authentication."""
        response = client.get("/api/v1/analytics/daily")
        assert response.status_code == 401


# ===========================================================================
# 2. Calendar
# ===========================================================================

class TestAnalyticsCalendar:
    """Test GET /api/v1/analytics/calendar endpoint."""

    def test_calendar_returns_200(self, client, auth_headers, db_session, seed_analytics_data):
        """Calendar endpoint should return 200 with year and month."""
        seed_analytics_data()
        response = client.get(
            "/api/v1/analytics/calendar?year=2025&month=1",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_calendar_empty_month(self, client, auth_headers):
        """Calendar for a month with no trades should return empty data."""
        response = client.get(
            "/api/v1/analytics/calendar?year=2024&month=6",
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_calendar_requires_params(self, client, auth_headers):
        """Calendar requires year and month params."""
        response = client.get(
            "/api/v1/analytics/calendar",
            headers=auth_headers,
        )
        assert response.status_code == 422  # Missing required params


# ===========================================================================
# 3. By Symbol
# ===========================================================================

class TestAnalyticsBySymbol:
    """Test GET /api/v1/analytics/by-symbol endpoint."""

    def test_by_symbol_returns_200(self, client, auth_headers, db_session, seed_analytics_data):
        """By-symbol endpoint should return 200."""
        seed_analytics_data()
        response = client.get("/api/v1/analytics/by-symbol", headers=auth_headers)
        assert response.status_code == 200

    def test_by_symbol_with_date_filter(self, client, auth_headers, db_session, seed_analytics_data):
        """Should support date range filtering."""
        seed_analytics_data()
        response = client.get(
            "/api/v1/analytics/by-symbol?from=2025-01-15&to=2025-01-15",
            headers=auth_headers,
        )
        assert response.status_code == 200


# ===========================================================================
# 4. By Strategy
# ===========================================================================

class TestAnalyticsByStrategy:
    """Test GET /api/v1/analytics/by-strategy endpoint."""

    def test_by_strategy_returns_200(self, client, auth_headers, db_session, seed_analytics_data):
        """By-strategy endpoint should return 200."""
        seed_analytics_data()
        response = client.get("/api/v1/analytics/by-strategy", headers=auth_headers)
        assert response.status_code == 200


# ===========================================================================
# 5. Performance Metrics
# ===========================================================================

class TestAnalyticsPerformance:
    """Test GET /api/v1/analytics/performance endpoint."""

    def test_performance_returns_200(self, client, auth_headers, db_session, seed_analytics_data):
        """Performance endpoint should return 200."""
        seed_analytics_data()
        response = client.get("/api/v1/analytics/performance", headers=auth_headers)
        assert response.status_code == 200

    def test_performance_returns_expected_metrics(self, client, auth_headers, db_session, seed_analytics_data):
        """Performance metrics should reflect trade_groups and daily summaries."""
        seed_analytics_data()
        response = client.get("/api/v1/analytics/performance", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["total_trades"] == 4
        assert data["trading_days"] == 2
        assert float(data["total_pnl"]) == pytest.approx(250)
        assert float(data["total_commissions"]) == pytest.approx(4)
        assert float(data["net_pnl"]) == pytest.approx(246)
        assert data["win_count"] == 1
        assert data["loss_count"] == 1
        assert data["win_rate"] == pytest.approx(50.0)
        assert float(data["avg_win"]) == pytest.approx(500)
        assert float(data["avg_loss"]) == pytest.approx(-250)
        assert data["win_loss_ratio"] == pytest.approx(2.0)
        assert float(data["expectancy"]) == pytest.approx(125)

    def test_performance_empty_db(self, client, auth_headers):
        """Performance metrics with no data should return sensible defaults."""
        response = client.get("/api/v1/analytics/performance", headers=auth_headers)
        assert response.status_code == 200

    def test_performance_with_date_filter(self, client, auth_headers, db_session, seed_analytics_data):
        """Performance metrics should support date range filtering."""
        seed_analytics_data()
        response = client.get(
            "/api/v1/analytics/performance?from=2025-01-15&to=2025-01-17",
            headers=auth_headers,
        )
        assert response.status_code == 200
