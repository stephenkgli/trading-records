"""Tradovate REST API ingester.

OAuth token management + REST endpoint for fills.
Supports live and demo environments.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.ingestion.base import BaseIngester
from backend.ingestion.normalizer import (
    ensure_utc,
    normalize_side,
    safe_decimal,
    safe_str,
)
from backend.models.import_log import ImportLog
from backend.schemas.import_result import ImportResult
from backend.schemas.trade import NormalizedTrade

logger = structlog.get_logger(__name__)

# Tradovate API base URLs
TRADOVATE_URLS = {
    "demo": "https://demo.tradovateapi.com/v1",
    "live": "https://live.tradovateapi.com/v1",
}

TRADOVATE_AUTH_URLS = {
    "demo": "https://demo.tradovateapi.com/v1/auth/accesstokenrequest",
    "live": "https://live.tradovateapi.com/v1/auth/accesstokenrequest",
}


class TradovateTokenManager:
    """Manages OAuth access tokens for Tradovate API.

    Caches tokens and refreshes proactively before expiration.
    """

    def __init__(
        self,
        environment: str = "demo",
        username: str = "",
        password: str = "",
        app_id: str = "trading-records",
        client_id: str = "",
        client_secret: str = "",
        device_id: str = "",
    ):
        self.environment = environment
        self.username = username
        self.password = password
        self.app_id = app_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.device_id = device_id

        self._token: str | None = None
        self._token_expiry: float = 0

    @property
    def auth_url(self) -> str:
        return TRADOVATE_AUTH_URLS.get(self.environment, TRADOVATE_AUTH_URLS["demo"])

    @property
    def base_url(self) -> str:
        return TRADOVATE_URLS.get(self.environment, TRADOVATE_URLS["demo"])

    def get_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
        # Check if current token is still valid (with 60s buffer)
        if self._token and time.time() < (self._token_expiry - 60):
            return self._token

        return self._refresh_token()

    def _refresh_token(self) -> str:
        """Request a new access token from Tradovate."""
        logger.info("tradovate_token_refresh", environment=self.environment)

        payload = {
            "name": self.username,
            "password": self.password,
            "appId": self.app_id,
            "appVersion": "1.0",
            "deviceId": self.device_id,
            "cid": self.client_id,
            "sec": self.client_secret,
        }

        with httpx.Client(timeout=30) as client:
            response = client.post(self.auth_url, json=payload)
            response.raise_for_status()

        data = response.json()

        if "accessToken" not in data:
            error_text = data.get("errorText", "Unknown error")
            raise RuntimeError(f"Tradovate auth failed: {error_text}")

        self._token = data["accessToken"]
        # Tradovate tokens typically expire in ~24 hours
        # Use expirationTime if provided, else default to 23 hours
        expiration = data.get("expirationTime")
        if expiration:
            try:
                exp_dt = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
                parsed_expiry = exp_dt.timestamp()
                # Some mocked/sandbox responses return stale timestamps.
                # Fall back to default TTL so token caching still works.
                if parsed_expiry <= time.time():
                    self._token_expiry = time.time() + 23 * 3600
                else:
                    self._token_expiry = parsed_expiry
            except (ValueError, TypeError):
                self._token_expiry = time.time() + 23 * 3600
        else:
            self._token_expiry = time.time() + 23 * 3600

        logger.info(
            "tradovate_token_acquired",
            expires_at=datetime.fromtimestamp(self._token_expiry, tz=timezone.utc).isoformat(),
        )

        return self._token


class TradovateIngester(BaseIngester):
    """Ingests trade data from Tradovate REST API."""

    source = "tradovate_api"

    def __init__(
        self,
        environment: str | None = None,
        username: str | None = None,
        password: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        device_id: str | None = None,
    ):
        self.token_manager = TradovateTokenManager(
            environment=environment or settings.tradovate_environment,
            username=username or settings.tradovate_username,
            password=password or settings.tradovate_password,
            app_id=settings.tradovate_app_id,
            client_id=client_id or settings.tradovate_client_id,
            client_secret=client_secret or settings.tradovate_client_secret,
            device_id=device_id or settings.tradovate_device_id,
        )
        # Cache for contract lookups
        self._contract_cache: dict[int, dict] = {}

    def check_idempotency(self, db: Session | None = None) -> bool:
        """Check if we already have a successful import for today."""
        own_session = db is None
        if own_session:
            db = SessionLocal()
        try:
            today_start = datetime.combine(date.today(), datetime.min.time()).replace(
                tzinfo=timezone.utc
            )
            stmt = select(ImportLog).where(
                ImportLog.source == self.source,
                ImportLog.status.in_(["success", "partial"]),
                ImportLog.started_at >= today_start,
            )
            result = db.execute(stmt).scalars().first()
            return result is not None
        finally:
            if own_session:
                db.close()

    def fetch_and_import(self, db: Session | None = None) -> ImportResult:
        """Full pipeline: check idempotency, fetch fills, normalize, import."""
        if self.check_idempotency(db):
            logger.info(
                "tradovate_skip_idempotent",
                message="Already imported today, skipping",
            )
            return ImportResult(
                import_log_id="00000000-0000-0000-0000-000000000000",
                source=self.source,
                status="skipped",
                records_total=0,
                records_imported=0,
                records_skipped_dup=0,
                records_failed=0,
            )

        if not self.token_manager.username or not self.token_manager.password:
            raise ValueError(
                "Tradovate credentials must be configured. "
                "Set TRADOVATE_USERNAME and TRADOVATE_PASSWORD."
            )

        # Get token
        token = self.token_manager.get_token()

        # Fetch fills
        fills = self._fetch_fills(token)

        # Normalize
        trades = self._normalize_fills(fills, token)

        # Import
        return self.import_records(trades, db=db)

    def _fetch_fills(self, token: str) -> list[dict]:
        """Fetch fills from Tradovate REST API."""
        base_url = self.token_manager.base_url
        headers = {"Authorization": f"Bearer {token}"}

        logger.info("tradovate_fetch_fills")

        with httpx.Client(timeout=30) as client:
            response = client.get(f"{base_url}/fill/list", headers=headers)
            response.raise_for_status()

        fills = response.json()
        logger.info("tradovate_fills_fetched", count=len(fills))
        return fills

    def _get_contract(self, contract_id: int, token: str) -> dict:
        """Fetch contract details (cached)."""
        if contract_id in self._contract_cache:
            return self._contract_cache[contract_id]

        base_url = self.token_manager.base_url
        headers = {"Authorization": f"Bearer {token}"}

        with httpx.Client(timeout=15) as client:
            response = client.get(
                f"{base_url}/contract/item",
                params={"id": contract_id},
                headers=headers,
            )
            if response.status_code == 200:
                contract = response.json()
                self._contract_cache[contract_id] = contract
                return contract

        return {}

    def _normalize_fills(
        self, fills: list[dict], token: str
    ) -> list[NormalizedTrade]:
        """Normalize Tradovate fills to NormalizedTrade records."""
        trades: list[NormalizedTrade] = []

        for fill in fills:
            try:
                trade = self._normalize_fill(fill, token)
                if trade:
                    trades.append(trade)
            except Exception as e:
                logger.error(
                    "tradovate_normalize_error",
                    fill_id=fill.get("id"),
                    error=str(e),
                )

        return trades

    def _normalize_fill(
        self, fill: dict, token: str
    ) -> NormalizedTrade | None:
        """Normalize a single Tradovate fill."""
        fill_id = fill.get("id")
        if fill_id is None:
            return None

        # Get contract info for symbol
        contract_id = fill.get("contractId")
        contract = self._get_contract(contract_id, token) if contract_id else {}
        symbol = safe_str(contract.get("name", ""))
        if not symbol:
            symbol = f"contract_{contract_id}"

        # Parse side
        action = safe_str(fill.get("action", ""))
        side = normalize_side(action)
        if side not in ("buy", "sell"):
            return None

        # Parse timestamp (Tradovate timestamps are UTC)
        timestamp_str = fill.get("timestamp", "")
        if not timestamp_str:
            return None

        try:
            if isinstance(timestamp_str, str):
                executed_at = datetime.fromisoformat(
                    timestamp_str.replace("Z", "+00:00")
                )
            else:
                executed_at = ensure_utc(timestamp_str)
        except (ValueError, TypeError):
            return None

        return NormalizedTrade(
            broker="tradovate",
            broker_exec_id=str(fill_id),
            account_id=str(fill.get("accountId", "")),
            symbol=symbol,
            underlying=safe_str(contract.get("productName")) or None,
            asset_class="future",  # Tradovate is futures-only
            side=side,
            quantity=abs(safe_decimal(fill.get("qty", "0"))),
            price=safe_decimal(fill.get("price", "0")),
            commission=abs(safe_decimal(fill.get("commission", "0"))),
            executed_at=executed_at,
            order_id=str(fill.get("orderId", "")) or None,
            exchange="TRADOVATE",
            currency="USD",
            raw_data=fill,
        )
