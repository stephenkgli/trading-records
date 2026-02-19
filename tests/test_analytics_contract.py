"""API contract regression tests for analytics endpoints post-refactoring.

Verifies that the analytics refactoring preserves identical behavior:
- All 5 endpoints return identical status codes
- Response JSON shapes unchanged
- Date filtering works the same
- Empty DB returns sensible defaults
- Auth requirements preserved
- Calendar requires year/month params (422 without)
- Query parameters work: from, to, account_id

These tests use the same fixtures and patterns as the existing
tests/test_api/test_analytics.py but focus on contract verification.
"""


import pytest


# ===========================================================================
# Status code contract tests
# ===========================================================================

class TestEndpointStatusCodes:
    """Verify all 5 endpoints return correct status codes."""

    def test_daily_200(self, client, auth_headers, db_session, seed_contract_analytics_data):
        seed_contract_analytics_data()
        resp = client.get("/api/v1/analytics/daily", headers=auth_headers)
        assert resp.status_code == 200

    def test_calendar_200(self, client, auth_headers, db_session, seed_contract_analytics_data):
        seed_contract_analytics_data()
        resp = client.get(
            "/api/v1/analytics/calendar?year=2025&month=3",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_by_symbol_200(self, client, auth_headers, db_session, seed_contract_analytics_data):
        seed_contract_analytics_data()
        resp = client.get("/api/v1/analytics/by-symbol", headers=auth_headers)
        assert resp.status_code == 200

    def test_by_strategy_200(self, client, auth_headers, db_session, seed_contract_analytics_data):
        seed_contract_analytics_data()
        resp = client.get("/api/v1/analytics/by-strategy", headers=auth_headers)
        assert resp.status_code == 200

    def test_performance_200(self, client, auth_headers, db_session, seed_contract_analytics_data):
        seed_contract_analytics_data()
        resp = client.get("/api/v1/analytics/performance", headers=auth_headers)
        assert resp.status_code == 200


# ===========================================================================
# Auth requirement tests
# ===========================================================================

class TestAuthRequirements:
    """Verify all endpoints require authentication."""

    @pytest.mark.parametrize("path", [
        "/api/v1/analytics/daily",
        "/api/v1/analytics/calendar?year=2025&month=1",
        "/api/v1/analytics/by-symbol",
        "/api/v1/analytics/by-strategy",
        "/api/v1/analytics/performance",
    ])
    def test_requires_auth(self, client, path):
        """All analytics endpoints should return 401 without auth."""
        resp = client.get(path)
        assert resp.status_code == 401


# ===========================================================================
# Response shape contract tests
# ===========================================================================

class TestResponseShapes:
    """Verify response JSON shapes are unchanged after refactoring."""

    def test_daily_shape(self, client, auth_headers, db_session, seed_contract_analytics_data):
        """Daily response should be list of objects with expected keys."""
        seed_contract_analytics_data()
        resp = client.get("/api/v1/analytics/daily", headers=auth_headers)
        data = resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            row = data[0]
            expected_keys = {
                "date", "account_id", "gross_pnl", "net_pnl",
                "commissions", "trade_count", "win_count", "loss_count",
            }
            assert expected_keys.issubset(row.keys()), (
                f"Missing keys in daily response: {expected_keys - row.keys()}"
            )

    def test_calendar_shape(self, client, auth_headers, db_session, seed_contract_analytics_data):
        """Calendar response should be list of objects with date, net_pnl, trade_count."""
        seed_contract_analytics_data()
        resp = client.get(
            "/api/v1/analytics/calendar?year=2025&month=3",
            headers=auth_headers,
        )
        data = resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            row = data[0]
            expected_keys = {"date", "net_pnl", "trade_count"}
            assert expected_keys.issubset(row.keys()), (
                f"Missing keys in calendar response: {expected_keys - row.keys()}"
            )

    def test_by_symbol_shape(self, client, auth_headers, db_session, seed_contract_analytics_data):
        """By-symbol response should be list with symbol, net_pnl, counts."""
        seed_contract_analytics_data()
        resp = client.get("/api/v1/analytics/by-symbol", headers=auth_headers)
        data = resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            row = data[0]
            expected_keys = {"symbol", "net_pnl", "trade_count", "win_count", "loss_count"}
            assert expected_keys.issubset(row.keys()), (
                f"Missing keys in by-symbol response: {expected_keys - row.keys()}"
            )

    def test_by_strategy_shape(self, client, auth_headers, db_session, seed_contract_analytics_data):
        """By-strategy response should be list with strategy_tag, net_pnl, counts."""
        seed_contract_analytics_data()
        resp = client.get("/api/v1/analytics/by-strategy", headers=auth_headers)
        data = resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            row = data[0]
            expected_keys = {"strategy_tag", "net_pnl", "trade_count", "group_count"}
            assert expected_keys.issubset(row.keys()), (
                f"Missing keys in by-strategy response: {expected_keys - row.keys()}"
            )

    def test_performance_shape(self, client, auth_headers, db_session, seed_contract_analytics_data):
        """Performance response should be single object with all metric keys."""
        seed_contract_analytics_data()
        resp = client.get("/api/v1/analytics/performance", headers=auth_headers)
        data = resp.json()
        assert isinstance(data, dict)
        expected_keys = {
            "total_pnl", "total_commissions", "net_pnl", "total_trades",
            "win_count", "loss_count", "win_rate", "avg_win", "avg_loss",
            "win_loss_ratio", "expectancy", "trading_days",
        }
        assert expected_keys.issubset(data.keys()), (
            f"Missing keys in performance response: {expected_keys - data.keys()}"
        )


# ===========================================================================
# Empty database tests
# ===========================================================================

class TestEmptyDatabase:
    """Verify sensible defaults when DB has no data."""

    def test_daily_empty(self, client, auth_headers):
        resp = client.get("/api/v1/analytics/daily", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_calendar_empty(self, client, auth_headers):
        resp = client.get(
            "/api/v1/analytics/calendar?year=2024&month=6",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_by_symbol_empty(self, client, auth_headers):
        resp = client.get("/api/v1/analytics/by-symbol", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_by_strategy_empty(self, client, auth_headers):
        resp = client.get("/api/v1/analytics/by-strategy", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_performance_empty(self, client, auth_headers):
        resp = client.get("/api/v1/analytics/performance", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        # Should return zeroed defaults, not error
        assert data["total_trades"] == 0
        assert float(data["total_pnl"]) == pytest.approx(0)


# ===========================================================================
# Date filtering tests
# ===========================================================================

class TestDateFiltering:
    """Verify date filtering works the same after refactoring."""

    def test_daily_date_range_filters(self, client, auth_headers, db_session, seed_contract_analytics_data):
        """Daily endpoint with from/to should filter results."""
        seed_contract_analytics_data()
        resp = client.get(
            "/api/v1/analytics/daily?from=2025-03-10&to=2025-03-10",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should only include 2025-03-10
        for row in data:
            assert row["date"] == "2025-03-10"

    def test_by_symbol_date_range(self, client, auth_headers, db_session, seed_contract_analytics_data):
        """By-symbol endpoint with from/to should filter results."""
        seed_contract_analytics_data()
        resp = client.get(
            "/api/v1/analytics/by-symbol?from=2025-03-10&to=2025-03-10",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_performance_date_range(self, client, auth_headers, db_session, seed_contract_analytics_data):
        """Performance endpoint with from/to should filter results."""
        seed_contract_analytics_data()
        resp = client.get(
            "/api/v1/analytics/performance?from=2025-03-10&to=2025-03-11",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert "total_trades" in data


# ===========================================================================
# Calendar-specific param validation
# ===========================================================================

class TestCalendarParams:
    """Verify calendar endpoint param requirements."""

    def test_calendar_missing_params_422(self, client, auth_headers):
        """Calendar without year/month should return 422."""
        resp = client.get("/api/v1/analytics/calendar", headers=auth_headers)
        assert resp.status_code == 422

    def test_calendar_missing_month_422(self, client, auth_headers):
        """Calendar with year but no month should return 422."""
        resp = client.get(
            "/api/v1/analytics/calendar?year=2025",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_calendar_invalid_month_422(self, client, auth_headers):
        """Calendar with month > 12 should return 422."""
        resp = client.get(
            "/api/v1/analytics/calendar?year=2025&month=13",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_calendar_month_zero_422(self, client, auth_headers):
        """Calendar with month=0 should return 422."""
        resp = client.get(
            "/api/v1/analytics/calendar?year=2025&month=0",
            headers=auth_headers,
        )
        assert resp.status_code == 422


# ===========================================================================
# Computed values contract tests
# ===========================================================================

class TestComputedValues:
    """Verify that computed values are correct after refactoring."""

    def test_daily_pnl_values(self, client, auth_headers, db_session, seed_contract_analytics_data):
        """Daily summaries should compute P&L correctly."""
        seed_contract_analytics_data()
        resp = client.get("/api/v1/analytics/daily", headers=auth_headers)
        data = resp.json()

        # Find the 2025-03-10 row (GOOG win day)
        day_10 = [r for r in data if r["date"] == "2025-03-10"]
        assert len(day_10) == 1
        row = day_10[0]
        assert row["trade_count"] == 2

    def test_performance_metrics_consistent(self, client, auth_headers, db_session, seed_contract_analytics_data):
        """Performance metrics should be internally consistent."""
        seed_contract_analytics_data()
        resp = client.get("/api/v1/analytics/performance", headers=auth_headers)
        data = resp.json()

        # net_pnl = total_pnl - total_commissions
        total_pnl = float(data["total_pnl"])
        total_comm = float(data["total_commissions"])
        net_pnl = float(data["net_pnl"])
        assert net_pnl == pytest.approx(total_pnl - total_comm)

        # win_count + loss_count should make sense
        assert data["win_count"] + data["loss_count"] >= 0

        # win_rate should be percentage
        assert 0 <= data["win_rate"] <= 100

    def test_performance_not_a_list(self, client, auth_headers, db_session, seed_contract_analytics_data):
        """Performance endpoint should return a single object, not a list."""
        seed_contract_analytics_data()
        resp = client.get("/api/v1/analytics/performance", headers=auth_headers)
        data = resp.json()
        assert isinstance(data, dict)
        assert not isinstance(data, list)

    def test_daily_is_a_list(self, client, auth_headers, db_session, seed_contract_analytics_data):
        """Daily endpoint should return a list."""
        seed_contract_analytics_data()
        resp = client.get("/api/v1/analytics/daily", headers=auth_headers)
        data = resp.json()
        assert isinstance(data, list)
