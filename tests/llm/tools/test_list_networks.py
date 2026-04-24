"""Tests for the list_networks LLM tool handler and metadata."""

from __future__ import annotations

from datetime import UTC, datetime

from pypsa_app.llm.tools import list_networks
from tests.conftest import FakeUser, make_network


def test_tool_metadata_shape():
    assert list_networks.NAME == "list_networks"
    assert len(list_networks.DESCRIPTION) > 40
    schema = list_networks.INPUT_SCHEMA
    assert schema["type"] == "object"
    assert set(schema["properties"]) == {"offset", "limit", "sort_by", "order"}
    assert schema["properties"]["limit"]["maximum"] == 100
    assert schema["properties"]["sort_by"]["enum"] == ["created_at", "name"]
    assert schema["properties"]["order"]["enum"] == ["asc", "desc"]
    assert schema["additionalProperties"] is False


def test_empty_envelope(monkeypatch, fake_user):
    monkeypatch.setattr(list_networks, "_query_networks", lambda **_: ([], 0))
    result = list_networks.handler(db=None, user=fake_user)
    assert result == {
        "networks": [],
        "total": 0,
        "offset": 0,
        "limit": 20,
        "returned": 0,
        "has_more": False,
        "next_offset": None,
        "sort_by": "created_at",
        "order": "desc",
    }


def test_single_page_no_more(monkeypatch, fake_user):
    nets = [make_network(owner_id=fake_user.id) for _ in range(3)]
    monkeypatch.setattr(list_networks, "_query_networks", lambda **_: (nets, 3))
    result = list_networks.handler(db=None, user=fake_user)
    assert result["total"] == 3
    assert result["returned"] == 3
    assert result["has_more"] is False
    assert result["next_offset"] is None
    assert len(result["networks"]) == 3


def test_has_more_and_next_offset(monkeypatch, fake_user):
    nets = [make_network(owner_id=fake_user.id) for _ in range(20)]
    monkeypatch.setattr(list_networks, "_query_networks", lambda **_: (nets, 50))
    result = list_networks.handler(db=None, user=fake_user, offset=0, limit=20)
    assert result["has_more"] is True
    assert result["next_offset"] == 20
    assert result["total"] == 50


def test_last_page_exactly_fills(monkeypatch, fake_user):
    nets = [make_network(owner_id=fake_user.id) for _ in range(10)]
    monkeypatch.setattr(list_networks, "_query_networks", lambda **_: (nets, 50))
    result = list_networks.handler(db=None, user=fake_user, offset=40, limit=10)
    assert result["has_more"] is False
    assert result["next_offset"] is None


def test_field_whitelist(monkeypatch, fake_user):
    net = make_network(owner_id=fake_user.id, name="Europe", filename="europe.nc")
    monkeypatch.setattr(list_networks, "_query_networks", lambda **_: ([net], 1))
    row = list_networks.handler(db=None, user=fake_user)["networks"][0]
    assert set(row.keys()) == {"id", "name", "created_at", "visibility", "is_owner"}


def test_name_falls_back_to_filename(monkeypatch, fake_user):
    net = make_network(owner_id=fake_user.id, name=None, filename="fallback.nc")
    monkeypatch.setattr(list_networks, "_query_networks", lambda **_: ([net], 1))
    row = list_networks.handler(db=None, user=fake_user)["networks"][0]
    assert row["name"] == "fallback.nc"


def test_is_owner_flag(monkeypatch, fake_user):
    other = FakeUser()
    mine = make_network(owner_id=fake_user.id, name="mine")
    theirs = make_network(owner_id=other.id, name="theirs")
    monkeypatch.setattr(
        list_networks, "_query_networks", lambda **_: ([mine, theirs], 2)
    )
    rows = list_networks.handler(db=None, user=fake_user)["networks"]
    by_name = {r["name"]: r for r in rows}
    assert by_name["mine"]["is_owner"] is True
    assert by_name["theirs"]["is_owner"] is False


def test_visibility_is_string_value(monkeypatch, fake_user):
    net = make_network(owner_id=fake_user.id, visibility="public")
    monkeypatch.setattr(list_networks, "_query_networks", lambda **_: ([net], 1))
    row = list_networks.handler(db=None, user=fake_user)["networks"][0]
    assert row["visibility"] == "public"


def test_naive_datetime_gets_z_suffix(monkeypatch, fake_user):
    net = make_network(owner_id=fake_user.id, created_at=datetime(2026, 1, 2, 3, 4, 5))
    monkeypatch.setattr(list_networks, "_query_networks", lambda **_: ([net], 1))
    row = list_networks.handler(db=None, user=fake_user)["networks"][0]
    assert row["created_at"].endswith("Z")


def test_aware_datetime_preserved(monkeypatch, fake_user):
    when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    net = make_network(owner_id=fake_user.id, created_at=when)
    monkeypatch.setattr(list_networks, "_query_networks", lambda **_: ([net], 1))
    row = list_networks.handler(db=None, user=fake_user)["networks"][0]
    assert row["created_at"] == when.isoformat()


def test_limit_clamped_to_100(monkeypatch, fake_user):
    captured: dict = {}

    def fake_query(**kw):
        captured.update(kw)
        return [], 0

    monkeypatch.setattr(list_networks, "_query_networks", fake_query)
    result = list_networks.handler(db=None, user=fake_user, limit=500)
    assert captured["limit"] == 100
    assert result["limit"] == 100


def test_negative_offset_clamped(monkeypatch, fake_user):
    captured: dict = {}

    def fake_query(**kw):
        captured.update(kw)
        return [], 0

    monkeypatch.setattr(list_networks, "_query_networks", fake_query)
    result = list_networks.handler(db=None, user=fake_user, offset=-5)
    assert captured["offset"] == 0
    assert result["offset"] == 0


def test_invalid_sort_by_falls_back(monkeypatch, fake_user):
    captured: dict = {}

    def fake_query(**kw):
        captured.update(kw)
        return [], 0

    monkeypatch.setattr(list_networks, "_query_networks", fake_query)
    list_networks.handler(db=None, user=fake_user, sort_by="garbage")
    assert captured["sort_by"] == "created_at"


def test_invalid_order_falls_back(monkeypatch, fake_user):
    captured: dict = {}

    def fake_query(**kw):
        captured.update(kw)
        return [], 0

    monkeypatch.setattr(list_networks, "_query_networks", fake_query)
    list_networks.handler(db=None, user=fake_user, order="sideways")
    assert captured["order"] == "desc"
