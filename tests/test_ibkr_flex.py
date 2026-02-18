"""
Integration tests for the IBKR Flex Query ingester.

Tests using mock HTTP responses:
1. Happy path — full flow from request to import
2. Poll retry — not-ready responses followed by success
3. Max attempts — exceed poll_max_attempts
4. HTTP errors — 4xx/5xx responses
5. Malformed XML — invalid XML in response
6. Idempotency — skip if already imported today
7. Circuit breaker — stop on error responses during polling

Reference: design-doc-final.md Section 5.3
"""

from unittest.mock import patch

import httpx
import pytest
import respx

from backend.ingestion.ibkr_flex import IBKRFlexIngester


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def ingester():
    """Create an IBKRFlexIngester with test config."""
    return IBKRFlexIngester(
        flex_token="test-flex-token",
        query_id="999999",
        poll_interval=0,  # no delay in tests
        poll_max_attempts=3,
    )


@pytest.fixture
def send_request_success_xml():
    """XML response for a successful SendRequest."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<FlexStatementResponse timestamp="2025-01-15 10:00:00">
    <Status>Success</Status>
    <ReferenceCode>REF12345</ReferenceCode>
    <Url>https://gdcdyn.interactivebrokers.com/Universal/servlet/FlexStatementService.GetStatement</Url>
</FlexStatementResponse>"""


@pytest.fixture
def poll_not_ready_xml():
    """XML response when the report is not yet ready."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<FlexStatementResponse timestamp="2025-01-15 10:00:05">
    <Status>Warn</Status>
    <ErrorCode>1019</ErrorCode>
    <ErrorMessage>Statement generation in progress. Please try again shortly.</ErrorMessage>
</FlexStatementResponse>"""


@pytest.fixture
def sample_flex_report(ibkr_flex_sample_xml):
    """The sample Flex report as bytes."""
    return ibkr_flex_sample_xml.encode()


# ===========================================================================
# Happy Path
# ===========================================================================

class TestFlexHappyPath:
    """Test the complete successful Flex Query import flow."""

    @respx.mock
    def test_full_flow(self, ingester, db_session, send_request_success_xml, sample_flex_report):
        """Full flow: SendRequest -> Poll -> GetStatement -> normalize -> import."""
        # Mock idempotency check to return False
        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*SendRequest.*").respond(
                content=send_request_success_xml,
                headers={"content-type": "text/xml"},
            )
            respx.get(url__regex=r".*GetStatement.*").respond(
                content=sample_flex_report,
                headers={"content-type": "text/xml"},
            )

            result = ingester.fetch_and_import(db=db_session)

        assert result is not None
        assert result.records_imported > 0
        assert result.status == "success"

    @respx.mock
    def test_trades_persisted(self, ingester, db_session, send_request_success_xml, sample_flex_report):
        """Trades should be persisted to the database after import."""
        from backend.models.trade import Trade

        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*SendRequest.*").respond(
                content=send_request_success_xml,
                headers={"content-type": "text/xml"},
            )
            respx.get(url__regex=r".*GetStatement.*").respond(
                content=sample_flex_report,
                headers={"content-type": "text/xml"},
            )

            ingester.fetch_and_import(db=db_session)

        count = db_session.query(Trade).count()
        assert count == 5  # 5 trades in sample XML


# ===========================================================================
# Poll Retry
# ===========================================================================

class TestFlexPollRetry:
    """Test polling behavior when report is not immediately ready."""

    @respx.mock
    def test_poll_retry_then_success(
        self, ingester, db_session, send_request_success_xml, poll_not_ready_xml, sample_flex_report
    ):
        """Should retry polling and succeed when report becomes ready."""
        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*SendRequest.*").respond(
                content=send_request_success_xml,
                headers={"content-type": "text/xml"},
            )

            poll_route = respx.get(url__regex=r".*GetStatement.*")
            poll_route.side_effect = [
                httpx.Response(200, content=poll_not_ready_xml, headers={"content-type": "text/xml"}),
                httpx.Response(200, content=poll_not_ready_xml, headers={"content-type": "text/xml"}),
                httpx.Response(200, content=sample_flex_report, headers={"content-type": "text/xml"}),
            ]

            result = ingester.fetch_and_import(db=db_session)

        assert result is not None
        assert result.records_imported > 0


# ===========================================================================
# Max Attempts Exceeded
# ===========================================================================

class TestFlexMaxAttempts:
    """Test behavior when poll_max_attempts is exceeded."""

    @respx.mock
    def test_max_attempts_exceeded(self, ingester, db_session, send_request_success_xml, poll_not_ready_xml):
        """Should raise RuntimeError when max poll attempts are exhausted."""
        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*SendRequest.*").respond(
                content=send_request_success_xml,
                headers={"content-type": "text/xml"},
            )
            respx.get(url__regex=r".*GetStatement.*").respond(
                content=poll_not_ready_xml,
                headers={"content-type": "text/xml"},
            )

            with pytest.raises(RuntimeError, match="timed out"):
                ingester.fetch_and_import(db=db_session)


# ===========================================================================
# HTTP Errors
# ===========================================================================

class TestFlexHTTPErrors:
    """Test handling of HTTP error responses."""

    @respx.mock
    def test_send_request_http_500(self, ingester, db_session):
        """HTTP 500 on SendRequest should raise an error."""
        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*SendRequest.*").respond(status_code=500)

            with pytest.raises(Exception):
                ingester.fetch_and_import(db=db_session)

    @respx.mock
    def test_send_request_http_401(self, ingester, db_session):
        """HTTP 401 (invalid token) on SendRequest should raise an error."""
        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*SendRequest.*").respond(status_code=401)

            with pytest.raises(Exception):
                ingester.fetch_and_import(db=db_session)

    @respx.mock
    def test_poll_http_client_error(self, ingester, db_session, send_request_success_xml):
        """HTTP 4xx during polling should raise immediately."""
        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*SendRequest.*").respond(
                content=send_request_success_xml,
                headers={"content-type": "text/xml"},
            )
            respx.get(url__regex=r".*GetStatement.*").respond(status_code=403)

            with pytest.raises(RuntimeError, match="client error"):
                ingester.fetch_and_import(db=db_session)


# ===========================================================================
# Malformed XML
# ===========================================================================

class TestFlexMalformedXML:
    """Test handling of malformed XML responses."""

    @respx.mock
    def test_malformed_xml_response(self, ingester, db_session, send_request_success_xml, ibkr_flex_malformed_xml):
        """Malformed XML in GetStatement should raise an error."""
        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*SendRequest.*").respond(
                content=send_request_success_xml,
                headers={"content-type": "text/xml"},
            )
            respx.get(url__regex=r".*GetStatement.*").respond(
                content=ibkr_flex_malformed_xml.encode(),
                headers={"content-type": "text/xml"},
            )

            with pytest.raises(Exception):
                ingester.fetch_and_import(db=db_session)


# ===========================================================================
# Idempotency
# ===========================================================================

class TestFlexIdempotency:
    """Test that duplicate imports for the same day are skipped."""

    def test_skip_if_already_imported(self, ingester, db_session):
        """If check_idempotency returns True, import should be skipped."""
        with patch.object(ingester, 'check_idempotency', return_value=True):
            result = ingester.fetch_and_import(db=db_session)

        assert result.status == "skipped"
        assert result.records_imported == 0


# ===========================================================================
# Circuit Breaker
# ===========================================================================

class TestFlexCircuitBreaker:
    """Test circuit breaker behavior on error responses during polling."""

    @respx.mock
    def test_error_response_stops_polling(self, ingester, db_session, send_request_success_xml):
        """An error XML response (not 'not ready') during polling should stop immediately."""
        error_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<FlexStatementResponse>
    <Status>Fail</Status>
    <ErrorCode>1020</ErrorCode>
    <ErrorMessage>Token has expired.</ErrorMessage>
</FlexStatementResponse>"""

        with patch.object(ingester, 'check_idempotency', return_value=False):
            respx.post(url__regex=r".*SendRequest.*").respond(
                content=send_request_success_xml,
                headers={"content-type": "text/xml"},
            )
            respx.get(url__regex=r".*GetStatement.*").respond(
                content=error_xml,
                headers={"content-type": "text/xml"},
            )

            with pytest.raises(RuntimeError, match="Token has expired"):
                ingester.fetch_and_import(db=db_session)
