"""Tradovate REST API import source."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.ingestion.sources.base import ImportSource, SourceRegistry
from backend.ingestion.tradovate import TradovateIngester

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.schemas.trade import NormalizedTrade


@SourceRegistry.register
class TradovateSource(ImportSource):
    """Import source for Tradovate REST API fills."""

    source_name = "tradovate_api"

    def __init__(
        self,
        environment: str | None = None,
        username: str | None = None,
        password: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        device_id: str | None = None,
    ) -> None:
        self._ingester = TradovateIngester(
            environment=environment,
            username=username,
            password=password,
            client_id=client_id,
            client_secret=client_secret,
            device_id=device_id,
        )

    def fetch_normalized_trades(
        self,
        *,
        db: Session | None = None,
        **kwargs: object,
    ) -> list[NormalizedTrade]:
        """Fetch fills from Tradovate API and return normalized trades.

        Respects idempotency (skips if already imported today).
        """
        if self._ingester.check_idempotency(db):
            return []

        if not self._ingester.token_manager.username or not self._ingester.token_manager.password:
            raise ValueError(
                "Tradovate credentials must be configured. "
                "Set TRADOVATE_USERNAME and TRADOVATE_PASSWORD."
            )

        token = self._ingester.token_manager.get_token()
        fills = self._ingester._fetch_fills(token)
        return self._ingester._normalize_fills(fills, token)
