"""LLM tool: return a structured summary of a single network.

Reads from the pre-extracted metadata cached on the ``Network`` row, so this
never opens the underlying NetCDF file. The free-form ``meta`` dict is *not*
returned in full — only its top-level keys plus its serialized size — because
on real PyPSA-Eur networks it can be tens of KB of nested config. A separate
tool covers full-meta retrieval.
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.models import Network, User
from pypsa_app.backend.permissions import can_access

NAME = "get_network_detail"

DESCRIPTION = (
    "Get a structured summary of a single PyPSA energy network the current "
    "user can see. Use this when the user asks about a specific network by "
    "id (typically obtained from list_networks).\n\n"
    "Returns id, name, created_at, visibility, ownership, file size, source "
    "run, dimension counts (timesteps/periods/scenarios), per-component "
    "counts (Bus, Generator, Line, ...), the carriers and countries present, "
    "and a small meta_summary listing top-level meta keys plus the meta blob "
    "size in bytes. The full meta dictionary is not included here — call the "
    "dedicated meta tool only if the user asks about run config, scenario "
    "settings, or other free-form annotations.\n\n"
    "If the network id is unknown OR the current user is not allowed to "
    "see it, returns {error: 'network_not_found'} — the same shape in both "
    "cases, so the existence of private networks is not leaked."
)

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "network_id": {
            "type": "string",
            "description": "UUID of the network. Get ids from list_networks.",
        },
    },
    "required": ["network_id"],
    "additionalProperties": False,
}


def _query_network(*, db: Session, network_id: UUID) -> Network | None:
    return (
        db.query(Network)
        .options(joinedload(Network.owner))
        .filter(Network.id == network_id)
        .first()
    )


def _isoformat(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat()


def _last_updated_at(network: Network) -> str | None:
    history = network.update_history or []
    return history[-1] if history else None


def _carrier_names(network: Network) -> list[str]:
    facets = network.facets or {}
    carriers = facets.get("carriers") or {}
    return sorted(carriers.keys()) if isinstance(carriers, dict) else []


def _countries(network: Network) -> list[str]:
    facets = network.facets or {}
    countries = facets.get("countries") or []
    return list(countries) if isinstance(countries, list) else []


def _meta_summary(network: Network) -> dict[str, Any]:
    meta = network.meta or {}
    return {
        "size_bytes": len(json.dumps(meta, default=str)),
        "keys": sorted(meta.keys()) if isinstance(meta, dict) else [],
    }


def _serialize(network: Network, user: User) -> dict[str, Any]:
    return {
        "id": str(network.id),
        "name": network.name or network.filename,
        "filename": network.filename,
        "created_at": _isoformat(network.created_at),
        "last_updated_at": _last_updated_at(network),
        "visibility": network.visibility.value,
        "is_owner": network.user_id == user.id,
        "file_size_bytes": network.file_size,
        "source_run_id": (
            str(network.source_run_id) if network.source_run_id else None
        ),
        "dimensions_count": network.dimensions_count or {},
        "components_count": network.components_count or {},
        "carriers": _carrier_names(network),
        "countries": _countries(network),
        "meta_summary": _meta_summary(network),
    }


def handler(
    *,
    db: Session,
    user: User,
    network_id: str,
) -> dict[str, Any]:
    """Return detail for one network the user can see, or a structured error."""
    try:
        parsed_id = UUID(str(network_id))
    except (ValueError, TypeError, AttributeError):
        return {"error": "invalid_network_id"}

    network = _query_network(db=db, network_id=parsed_id)
    if network is None or not can_access(user, network):
        return {"error": "network_not_found"}

    return _serialize(network, user)
