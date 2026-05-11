"""Shared pagination and sorting utilities for list endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from fastapi import HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Select, func

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class PaginationParams(BaseModel):
    offset: int = 0
    limit: int = 100
    sort_by: str | None = None
    sort_dir: Literal["asc", "desc"] = Query("asc")


def apply_pagination(
    query: Select,
    model: type,
    params: PaginationParams,
    session: Session,
    allowed_sort_fields: set[str],
    default_sort: str = "created_at",
    default_sort_dir: Literal["asc", "desc"] = "desc",
) -> tuple[Select, int]:
    """Apply sort + offset/limit to a query and return (query, total_count)."""
    total = session.scalar(query.with_only_columns(func.count()).order_by(None))

    sort_col_name = params.sort_by or default_sort
    if sort_col_name not in allowed_sort_fields:
        raise HTTPException(422, f"Cannot sort by {sort_col_name!r}")
    sort_col = getattr(model, sort_col_name)
    direction = params.sort_dir if params.sort_by else default_sort_dir
    sort_col = sort_col.desc() if direction == "desc" else sort_col.asc()
    query = query.order_by(sort_col)

    query = query.offset(params.offset).limit(params.limit)
    return query, total or 0
