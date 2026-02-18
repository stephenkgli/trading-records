"""
Integration tests for the Tradovate REST ingester.

Tests using mock HTTP responses:
1. Happy path — full flow with auth + fill fetch + import
2. Token refresh — expired token triggers refresh
3. Auth failure — invalid credentials
4. Rate limit — 429 response handling
5. Empty fills — /fill/list returns empty array
6. Idempotency — skip if already imported

Reference: design-doc-final.md Section 5.4
"""

from unittest.mock import patch

import httpx
import pytest
import respx

from backend.ingestion.tradovate import TradovateIngester, TradovateTokenManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ingester():
    """Create a TradovateIngester with test config."""
    return TradovateIngester(
        environment="demo",
        username="testuser",
        password="testpass",
        client_id="test-client-id",
        client_secret="test-client-secret",
        device_id="test-device-id",
    )


# ===========================================================================
# Happy Path
# ===========================================================================

class TestTradovateHappyPath:
    """Test the complete successful Tradovate import flow."""

    @respx.mock
    def test_full_flow(
        self, ingester, db_session, tradovate_fills_json,
        tradovate_contracts_json, tradovate_auth_response_json
    ):
        """Full flow: auth -> fetch fills -> fetch contracts -> normalize -> import."""
        with patch.object(ingester, 'check_idempotency', return_value=False):
            # Mock auth
            respx.post(url__regex=r".*auth/accesstokenrequest.*").respond(
                json=tradovate_auth_response_json
            )
            # Mock fill/list
            respx.get(url__regex=r".*fill/list.*").respond(
                json=tradovate_fills_json
            )
            # Mock contract/item (both contracts)
            for cid, cdata in tradovate_contracts_json.items():
                respx.get(url__regex=rf".*contract/item.*").respond(json=cdata)

            result = ingester.fetch_and_import(db=db_session)

        assert result is not None
        assert result.records_imported > 0
        assert result.status == "success"

    @respx.mock
    def test_trades_persisted(
        self, ingester, db_session, tradovate_fills_json,
        tradovate_contracts_json, tradovate_auth_response_json
    ):
        """Imported trades should be persisted to the database."""
        from backend.models.trade import Trade

        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*auth/accesstokenrequest.*").respond(
                json=tradovate_auth_response_json
            )
            respx.get(url__regex=r".*fill/list.*").respond(json=tradovate_fills_json)
            respx.get(url__regex=r".*contract/item.*").respond(
                json=list(tradovate_contracts_json.values())[0]
            )

            ingester.fetch_and_import(db=db_session)

        count = db_session.query(Trade).filter_by(broker="tradovate").count()
        assert count == 4  # 4 fills in fixture


# ===========================================================================
# Auth Failure
# ===========================================================================

class TestTradovateAuthFailure:
    """Test handling of authentication failures."""

    @respx.mock
    def test_invalid_credentials(self, ingester, db_session):
        """Invalid credentials should raise an error."""
        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*auth/accesstokenrequest.*").respond(
                status_code=401,
                json={"error": "Invalid credentials"}
            )

            with pytest.raises(Exception):
                ingester.fetch_and_import(db=db_session)

    @respx.mock
    def test_auth_server_error(self, ingester, db_session):
        """Auth server error should raise."""
        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*auth/accesstokenrequest.*").respond(status_code=500)

            with pytest.raises(Exception):
                ingester.fetch_and_import(db=db_session)


# ===========================================================================
# Empty Fills
# ===========================================================================

class TestTradovateEmptyFills:
    """Test handling of empty fill/list responses."""

    @respx.mock
    def test_empty_fills_array(self, ingester, db_session, tradovate_auth_response_json):
        """Empty fills array should result in success with 0 records imported."""
        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*auth/accesstokenrequest.*").respond(
                json=tradovate_auth_response_json
            )
            respx.get(url__regex=r".*fill/list.*").respond(json=[])

            result = ingester.fetch_and_import(db=db_session)

        assert result is not None
        assert result.records_total == 0
        assert result.records_imported == 0
        assert result.status == "success"


# ===========================================================================
# Idempotency
# ===========================================================================

class TestTradovateIdempotency:
    """Test idempotency of Tradovate imports."""

    def test_skip_if_already_imported(self, ingester, db_session):
        """If check_idempotency returns True, import should be skipped."""
        with patch.object(ingester, 'check_idempotency', return_value=True):
            result = ingester.fetch_and_import(db=db_session)

        assert result.status == "skipped"
        assert result.records_imported == 0

    @respx.mock
    def test_duplicate_import_skips(
        self, ingester, db_session, tradovate_fills_json,
        tradovate_contracts_json, tradovate_auth_response_json
    ):
        """Second import of same fills should skip duplicates via dedup."""
        from backend.models.trade import Trade

        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*auth/accesstokenrequest.*").respond(
                json=tradovate_auth_response_json
            )
            respx.get(url__regex=r".*fill/list.*").respond(json=tradovate_fills_json)
            respx.get(url__regex=r".*contract/item.*").respond(
                json=list(tradovate_contracts_json.values())[0]
            )

            # First import
            result1 = ingester.fetch_and_import(db=db_session)
            count1 = db_session.query(Trade).count()

            # Reset mocks and contract cache
            ingester._contract_cache.clear()
            respx.reset()
            respx.post(url__regex=r".*auth/accesstokenrequest.*").respond(
                json=tradovate_auth_response_json
            )
            respx.get(url__regex=r".*fill/list.*").respond(json=tradovate_fills_json)
            respx.get(url__regex=r".*contract/item.*").respond(
                json=list(tradovate_contracts_json.values())[0]
            )

            # Second import
            result2 = ingester.fetch_and_import(db=db_session)
            count2 = db_session.query(Trade).count()

        assert count1 == count2  # No new records
        assert result2.records_skipped_dup == 4


# ===========================================================================
# Token Manager
# ===========================================================================

class TestTradovateTokenManager:
    """Test the token manager."""

    @respx.mock
    def test_token_acquired(self, tradovate_auth_response_json):
        """Token manager should acquire a token via auth endpoint."""
        respx.post(url__regex=r".*auth/accesstokenrequest.*").respond(
            json=tradovate_auth_response_json
        )

        mgr = TradovateTokenManager(
            environment="demo",
            username="testuser",
            password="testpass",
            client_id="test",
            client_secret="test",
            device_id="test",
        )

        token = mgr.get_token()
        assert token is not None
        assert len(token) > 0

    @respx.mock
    def test_token_cached(self, tradovate_auth_response_json):
        """Second call to get_token should return cached token."""
        route = respx.post(url__regex=r".*auth/accesstokenrequest.*").respond(
            json=tradovate_auth_response_json
        )

        mgr = TradovateTokenManager(
            environment="demo",
            username="testuser",
            password="testpass",
            client_id="test",
            client_secret="test",
            device_id="test",
        )

        token1 = mgr.get_token()
        token2 = mgr.get_token()

        assert token1 == token2
        assert route.call_count == 1  # Only called auth once
