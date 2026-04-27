"""Tests for the get_network_detail LLM tool handler and metadata."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pypsa_app.llm.tools import get_network_detail
from tests.conftest import FakeUser, make_network


def _patch(monkeypatch, *, network, allowed: bool = True) -> None:
    """Stub out DB query and permission check for the handler."""
    monkeypatch.setattr(get_network_detail, "_query_network", lambda **_: network)
    monkeypatch.setattr(get_network_detail, "can_access", lambda _u, _r: allowed)


def test_tool_metadata_shape():
    assert get_network_detail.NAME == "get_network_detail"
    assert len(get_network_detail.DESCRIPTION) > 100
    schema = get_network_detail.INPUT_SCHEMA
    assert schema["type"] == "object"
    assert schema["required"] == ["network_id"]
    assert schema["properties"]["network_id"]["type"] == "string"
    assert schema["additionalProperties"] is False


def test_invalid_uuid_returns_error(fake_user):
    out = get_network_detail.handler(db=None, user=fake_user, network_id="not-a-uuid")
    assert out == {"error": "invalid_network_id"}


def test_unknown_network_returns_not_found(monkeypatch, fake_user):
    _patch(monkeypatch, network=None)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(uuid4()))
    assert out == {"error": "network_not_found"}


def test_unauthorized_uses_same_error_as_unknown(monkeypatch, fake_user):
    """Don't leak existence of private networks the user can't see."""
    other_owner = FakeUser()
    private_net = make_network(owner_id=other_owner.id, visibility="private")
    _patch(monkeypatch, network=private_net, allowed=False)
    out = get_network_detail.handler(
        db=None, user=fake_user, network_id=str(private_net.id)
    )
    assert out == {"error": "network_not_found"}


def test_happy_path_field_whitelist(monkeypatch, fake_user):
    net = make_network(
        owner_id=fake_user.id,
        name="Europe",
        filename="europe.nc",
        file_size=12345,
        dimensions_count={"timesteps": 168, "periods": 0, "scenarios": 0},
        components_count={"Bus": 9, "Generator": 6},
        facets={"carriers": {"AC": {}, "DC": {}}, "countries": ["DE", "NO"]},
        meta={"run": "x", "config": "y"},
        update_history=["2026-04-26T10:00:00+00:00"],
    )
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert set(out.keys()) == {
        "id",
        "name",
        "filename",
        "created_at",
        "last_updated_at",
        "visibility",
        "is_owner",
        "file_size_bytes",
        "source_run_id",
        "dimensions_count",
        "components_count",
        "carriers",
        "countries",
        "meta_summary",
    }


def test_name_falls_back_to_filename(monkeypatch, fake_user):
    net = make_network(owner_id=fake_user.id, name=None, filename="fallback.nc")
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert out["name"] == "fallback.nc"


def test_is_owner_true_for_owner(monkeypatch, fake_user):
    net = make_network(owner_id=fake_user.id)
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert out["is_owner"] is True


def test_is_owner_false_for_public_network(monkeypatch, fake_user):
    other = FakeUser()
    net = make_network(owner_id=other.id, visibility="public")
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert out["is_owner"] is False
    assert out["visibility"] == "public"


def test_carriers_returns_sorted_names_only(monkeypatch, fake_user):
    """Carrier attributes (color, co2, etc.) must not leak into the result."""
    net = make_network(
        owner_id=fake_user.id,
        facets={
            "carriers": {
                "DC": {"color": "purple", "co2_emissions": 0.0},
                "AC": {"color": "orange", "co2_emissions": 0.0},
            }
        },
    )
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert out["carriers"] == ["AC", "DC"]


def test_countries_default_empty(monkeypatch, fake_user):
    net = make_network(owner_id=fake_user.id, facets={"carriers": {}})
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert out["countries"] == []


def test_meta_summary_excludes_values(monkeypatch, fake_user):
    """The point of meta_summary is to avoid context blow-up — only keys+size."""
    big_value = "x" * 5000
    net = make_network(
        owner_id=fake_user.id,
        meta={"big": big_value, "small": "ok"},
    )
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    summary = out["meta_summary"]
    assert summary["keys"] == ["big", "small"]
    assert summary["size_bytes"] > 5000
    assert big_value not in str(out)


def test_meta_summary_handles_empty_meta(monkeypatch, fake_user):
    net = make_network(owner_id=fake_user.id, meta=None)
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert out["meta_summary"] == {"size_bytes": 2, "keys": []}


def test_naive_datetime_gets_z_suffix(monkeypatch, fake_user):
    net = make_network(owner_id=fake_user.id, created_at=datetime(2026, 1, 2, 3, 4, 5))
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert out["created_at"].endswith("Z")


def test_aware_datetime_preserved(monkeypatch, fake_user):
    when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    net = make_network(owner_id=fake_user.id, created_at=when)
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert out["created_at"] == when.isoformat()


def test_last_updated_at_takes_latest_history_entry(monkeypatch, fake_user):
    net = make_network(
        owner_id=fake_user.id,
        update_history=[
            "2026-04-20T10:00:00+00:00",
            "2026-04-25T10:00:00+00:00",
        ],
    )
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert out["last_updated_at"] == "2026-04-25T10:00:00+00:00"


def test_last_updated_at_none_when_no_history(monkeypatch, fake_user):
    net = make_network(owner_id=fake_user.id, update_history=None)
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert out["last_updated_at"] is None


def test_source_run_id_serialized_as_string(monkeypatch, fake_user):
    run_id = uuid4()
    net = make_network(owner_id=fake_user.id, source_run_id=run_id)
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert out["source_run_id"] == str(run_id)


def test_source_run_id_none_when_unset(monkeypatch, fake_user):
    net = make_network(owner_id=fake_user.id, source_run_id=None)
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=str(net.id))
    assert out["source_run_id"] is None


def test_uuid_object_input_accepted(monkeypatch, fake_user):
    """Anthropic SDK passes strings, but defensive parse should not reject UUIDs."""
    net = make_network(owner_id=fake_user.id)
    _patch(monkeypatch, network=net)
    out = get_network_detail.handler(db=None, user=fake_user, network_id=net.id)
    assert "error" not in out
