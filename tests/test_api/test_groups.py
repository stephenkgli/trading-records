"""Tests for trade groups API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal


class TestGroupsAPI:
    def test_groups_recompute_and_list(self, client, auth_headers, db_session, seed_group_trades):
        seed_group_trades()

        recompute_resp = client.post("/api/v1/groups/recompute", headers=auth_headers)
        assert recompute_resp.status_code == 200
        recompute_data = recompute_resp.json()
        assert recompute_data["groups_created"] >= 1

        list_resp = client.get("/api/v1/groups", headers=auth_headers)
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert list_data["total"] >= 1
        assert len(list_data["groups"]) >= 1

    def test_group_detail_and_patch(self, client, auth_headers, db_session, seed_group_trades):
        seed_group_trades()
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

    def test_groups_sort_and_pagination_are_global(
        self, client, auth_headers, db_session, make_trade_group
    ):
        make_trade_group(
            symbol="AAPL",
            realized_pnl=Decimal("30"),
            opened_at=datetime(2025, 1, 3, 10, 0, 0, tzinfo=timezone.utc),
        )
        make_trade_group(
            symbol="MSFT",
            realized_pnl=Decimal("10"),
            opened_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        )
        make_trade_group(
            symbol="GOOG",
            realized_pnl=Decimal("20"),
            opened_at=datetime(2025, 1, 2, 10, 0, 0, tzinfo=timezone.utc),
        )
        db_session.commit()

        page1 = client.get(
            "/api/v1/groups?sort=opened_at&order=asc&page=1&per_page=1",
            headers=auth_headers,
        )
        page2 = client.get(
            "/api/v1/groups?sort=opened_at&order=asc&page=2&per_page=1",
            headers=auth_headers,
        )
        page3 = client.get(
            "/api/v1/groups?sort=opened_at&order=asc&page=3&per_page=1",
            headers=auth_headers,
        )

        assert page1.status_code == 200
        assert page2.status_code == 200
        assert page3.status_code == 200
        assert page1.json()["groups"][0]["symbol"] == "MSFT"
        assert page2.json()["groups"][0]["symbol"] == "GOOG"
        assert page3.json()["groups"][0]["symbol"] == "AAPL"

    def test_groups_sort_by_realized_pnl_desc(
        self, client, auth_headers, db_session, make_trade_group
    ):
        make_trade_group(symbol="AAPL", realized_pnl=Decimal("30"))
        make_trade_group(symbol="MSFT", realized_pnl=Decimal("-10"))
        make_trade_group(symbol="GOOG", realized_pnl=Decimal("20"))
        db_session.commit()

        resp = client.get(
            "/api/v1/groups?sort=realized_pnl&order=desc&page=1&per_page=3",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        symbols = [g["symbol"] for g in resp.json()["groups"]]
        assert symbols == ["AAPL", "GOOG", "MSFT"]

    def test_groups_filter_by_asset_classes(
        self, client, auth_headers, db_session, make_trade_group
    ):
        make_trade_group(symbol="AAPL", asset_class="stock")
        make_trade_group(symbol="MESZ5", asset_class="future")
        make_trade_group(symbol="AAPL250117C150", asset_class="option")
        db_session.commit()

        resp = client.get(
            "/api/v1/groups?asset_classes=Stock,FUTURE",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["total"] == 2
        assert {g["asset_class"] for g in data["groups"]} == {"stock", "future"}

    def test_groups_filter_empty_asset_classes_returns_empty(
        self, client, auth_headers, db_session, make_trade_group
    ):
        make_trade_group(symbol="AAPL", asset_class="stock")
        db_session.commit()

        resp = client.get("/api/v1/groups?asset_classes=", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["total"] == 0
        assert data["groups"] == []
