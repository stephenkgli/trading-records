"""Tests for trade groups API endpoints."""

from __future__ import annotations



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
