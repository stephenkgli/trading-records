"""Tests for trade groups API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from backend.models.trade import Trade


def _seed_group_trades(db_session) -> None:
    trades = [
        Trade(
            id=uuid.uuid4(),
            broker="ibkr",
            broker_exec_id="GRP0001",
            account_id="U1234567",
            symbol="AAPL",
            asset_class="stock",
            side="buy",
            quantity=Decimal("100"),
            price=Decimal("100"),
            commission=Decimal("1"),
            executed_at=datetime(2025, 1, 10, 10, 0, 0, tzinfo=timezone.utc),
            currency="USD",
            raw_data={},
        ),
        Trade(
            id=uuid.uuid4(),
            broker="ibkr",
            broker_exec_id="GRP0002",
            account_id="U1234567",
            symbol="AAPL",
            asset_class="stock",
            side="sell",
            quantity=Decimal("100"),
            price=Decimal("110"),
            commission=Decimal("1"),
            executed_at=datetime(2025, 1, 10, 14, 0, 0, tzinfo=timezone.utc),
            currency="USD",
            raw_data={},
        ),
        Trade(
            id=uuid.uuid4(),
            broker="ibkr",
            broker_exec_id="GRP0003",
            account_id="U1234567",
            symbol="MSFT",
            asset_class="stock",
            side="buy",
            quantity=Decimal("50"),
            price=Decimal("300"),
            commission=Decimal("1"),
            executed_at=datetime(2025, 1, 11, 10, 0, 0, tzinfo=timezone.utc),
            currency="USD",
            raw_data={},
        ),
    ]
    db_session.add_all(trades)
    db_session.flush()


class TestGroupsAPI:
    def test_groups_recompute_and_list(self, client, auth_headers, db_session):
        _seed_group_trades(db_session)

        recompute_resp = client.post("/api/v1/groups/recompute", headers=auth_headers)
        assert recompute_resp.status_code == 200
        recompute_data = recompute_resp.json()
        assert recompute_data["groups_created"] >= 1

        list_resp = client.get("/api/v1/groups", headers=auth_headers)
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["total"] >= 1
        assert len(list_data["groups"]) >= 1

    def test_group_detail_and_patch(self, client, auth_headers, db_session):
        _seed_group_trades(db_session)
        client.post("/api/v1/groups/recompute", headers=auth_headers)

        groups_resp = client.get("/api/v1/groups?symbol=AAPL", headers=auth_headers)
        group_id = groups_resp.json()["groups"][0]["id"]

        detail_resp = client.get(f"/api/v1/groups/{group_id}", headers=auth_headers)
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert len(detail_data["legs"]) >= 2

        patch_resp = client.patch(
            f"/api/v1/groups/{group_id}",
            headers=auth_headers,
            json={"strategy_tag": "swing", "notes": "test-note"},
        )
        assert patch_resp.status_code == 200
        patched = patch_resp.json()
        assert patched["strategy_tag"] == "swing"
        assert patched["notes"] == "test-note"

    def test_groups_requires_auth(self, client):
        assert client.get("/api/v1/groups").status_code == 401
        assert client.post("/api/v1/groups/recompute").status_code == 401
