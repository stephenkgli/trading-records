"""IBKR Flex Query import source."""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.ingestion.ibkr_flex import IBKRFlexIngester
from backend.ingestion.sources.base import ImportSource, SourceRegistry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from backend.schemas.trade import NormalizedTrade


@SourceRegistry.register
class FlexQuerySource(ImportSource):
    """Import source for IBKR Flex Query XML reports."""

    source_name = "flex_query"

    def __init__(
        self,
        flex_token: str | None = None,
        query_id: str | None = None,
        poll_interval: int | None = None,
        poll_max_attempts: int | None = None,
    ) -> None:
        self._ingester = IBKRFlexIngester(
            flex_token=flex_token,
            query_id=query_id,
            poll_interval=poll_interval,
            poll_max_attempts=poll_max_attempts,
        )

    def fetch_normalized_trades(
        self,
        *,
        db: Session | None = None,
        **kwargs: object,
    ) -> list[NormalizedTrade]:
        """Fetch Flex Query XML and return normalized trades.

        Performs the full REST flow: send request -> poll -> parse XML.
        Respects idempotency (skips if already imported today).
        """
        if self._ingester.check_idempotency(db):
            return []

        if not self._ingester.flex_token or not self._ingester.query_id:
            raise ValueError(
                "IBKR Flex token and query ID must be configured. "
                "Set IBKR_FLEX_TOKEN and IBKR_QUERY_ID."
            )

        reference_code = self._ingester._send_request()
        xml_data = self._ingester._poll_for_report(reference_code)
        return self._ingester._parse_flex_xml(xml_data)
