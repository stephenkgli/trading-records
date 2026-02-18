"""Custom application exceptions."""

from __future__ import annotations

from typing import Any

from starlette import status


class AppException(Exception):
    """Base application exception with structured error metadata."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.context = context or {}
