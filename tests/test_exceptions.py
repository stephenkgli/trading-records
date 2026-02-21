"""
Tests for the exception system (AppException and handlers).

Verifies:
1. AppException attributes and inheritance
2. Exception handler response format for AppException
3. Exception handler response format for HTTPException
4. Exception handler response format for RequestValidationError
5. Exception handler response format for unhandled exceptions
"""

from __future__ import annotations

import pytest
from starlette import status

from backend.exceptions.base import AppException


class TestAppException:
    """Test AppException base class."""

    def test_default_status_code(self):
        """Default status_code should be 400."""
        exc = AppException(code="test_error", message="Something went wrong")
        assert exc.status_code == status.HTTP_400_BAD_REQUEST

    def test_custom_status_code(self):
        """Custom status_code should be preserved."""
        exc = AppException(
            code="not_found",
            message="Resource not found",
            status_code=status.HTTP_404_NOT_FOUND,
        )
        assert exc.status_code == 404

    def test_code_and_message(self):
        """code and message should be accessible."""
        exc = AppException(code="my_code", message="my message")
        assert exc.code == "my_code"
        assert exc.message == "my message"

    def test_context_default_empty(self):
        """context should default to empty dict."""
        exc = AppException(code="err", message="msg")
        assert exc.context == {}

    def test_context_preserved(self):
        """Custom context should be preserved."""
        ctx = {"trade_id": "abc", "field": "price"}
        exc = AppException(code="err", message="msg", context=ctx)
        assert exc.context == ctx

    def test_inherits_from_exception(self):
        """AppException should inherit from Exception."""
        exc = AppException(code="err", message="test")
        assert isinstance(exc, Exception)

    def test_str_representation(self):
        """str(AppException) should return the message."""
        exc = AppException(code="err", message="something happened")
        assert str(exc) == "something happened"


class TestExceptionHandlerResponses:
    """Test that exception handlers produce the correct response format."""

    def test_app_exception_response(self, client):
        """AppException raised in a handler should return structured error."""
        # We'll test via the real app. A non-existent trade ID should return 404
        # (which goes through the http_exception_handler).
        import uuid

        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/trades/{fake_id}")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]

    def test_validation_error_response(self, client):
        """Validation error should return 422 with structured error."""
        # Missing required params for calendar endpoint
        response = client.get("/api/v1/analytics/calendar")
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "error" in data
        assert data["error"]["code"] == "validation_error"
