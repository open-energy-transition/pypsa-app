"""LLM tool: list networks visible to the current user, with pagination."""

from datetime import datetime
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.models import Network, Permission, User, Visibility
from pypsa_app.backend.permissions import has_permission

NAME = "list_networks"

DESCRIPTION = (
    "List PyPSA energy networks visible to the current user, with pagination. "
    "Returns each network's id, name, creation date, visibility, and whether "
    "the current user owns it. Networks marked is_owner=false are public "
    "networks owned by other users.\n\n"
    "Use when the user asks about their networks, wants an overview, or needs "
    "network ids before drilling in.\n\n"
    "Results are paginated. Default page size is 20, maximum 100. The response "
    "includes total, has_more, and next_offset. To see the next page, call "
    "again with offset=next_offset and the same sort_by and order. Sort by "
    "created_at (default) or name; order desc (default) or asc."
)

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "offset": {
            "type": "integer",
            "minimum": 0,
            "default": 0,
            "description": "Number of networks to skip (for pagination).",
        },
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "default": 20,
            "description": "Maximum number of networks to return (1-100).",
        },
        "sort_by": {
            "type": "string",
            "enum": ["created_at", "name"],
            "default": "created_at",
            "description": "Field to sort by.",
        },
        "order": {
            "type": "string",
            "enum": ["asc", "desc"],
            "default": "desc",
            "description": "Sort direction.",
        },
    },
    "additionalProperties": False,
}

_SORT_COLUMNS = {
    "created_at": Network.created_at,
    "name": Network.name,
}


def _query_networks(
    *,
    db: Session,
    user: User,
    offset: int,
    limit: int,
    sort_by: str,
    order: str,
) -> tuple[list[Network], int]:
    query = db.query(Network).options(joinedload(Network.owner))
    if not has_permission(user, Permission.NETWORKS_MANAGE_ALL):
        query = query.filter(
            or_(
                Network.user_id == user.id,
                Network.visibility == Visibility.PUBLIC,
            )
        )
    total = query.count()
    sort_col = _SORT_COLUMNS[sort_by]
    sort_col = sort_col.desc() if order == "desc" else sort_col.asc()
    networks = query.order_by(sort_col).offset(offset).limit(limit).all()
    return networks, total


def _isoformat(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.isoformat() + "Z"
    return dt.isoformat()


def _serialize(network: Network, user: User) -> dict[str, Any]:
    return {
        "id": str(network.id),
        "name": network.name or network.filename,
        "created_at": _isoformat(network.created_at),
        "visibility": network.visibility.value,
        "is_owner": network.user_id == user.id,
    }


def handler(
    *,
    db: Session,
    user: User,
    offset: int = 0,
    limit: int = 20,
    sort_by: str = "created_at",
    order: str = "desc",
) -> dict[str, Any]:
    """List networks visible to ``user``, paginated and sorted."""
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    if sort_by not in _SORT_COLUMNS:
        sort_by = "created_at"
    if order not in ("asc", "desc"):
        order = "desc"

    networks, total = _query_networks(
        db=db,
        user=user,
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        order=order,
    )
    returned = len(networks)
    has_more = (offset + returned) < total
    next_offset = (offset + returned) if has_more else None

    return {
        "networks": [_serialize(n, user) for n in networks],
        "total": total,
        "offset": offset,
        "limit": limit,
        "returned": returned,
        "has_more": has_more,
        "next_offset": next_offset,
        "sort_by": sort_by,
        "order": order,
    }
