"""LLM tool: aggregate statistics for a PyPSA network.

Returns pre-aggregated statistics grouped by category so the LLM can answer
questions about capacity, costs, energy flows, performance, and economics
without ever receiving raw time-series data.

Key design choices:
- ``groupby_time`` chooses **how** to aggregate (sum / mean / max / min),
  never **whether** — raw time-series is explicitly forbidden because it
  would blow the LLM context window.
- ``groupby`` chooses **what dimension** to group results by.  The default
  ``"carrier"`` matches PyPSA's default and is the most concise.  Using
  ``"country"`` or ``"bus"`` produces more rows but lets the LLM answer
  spatial questions.
- ``groupby_method`` chooses **how to aggregate within groups** (e.g. mean
  across carriers).  Default is ``"sum"``, matching PyPSA.
- There is no ``query`` / ``country`` filter parameter because PyPSA's
  statistics methods do not accept a ``query`` kwarg — that is only
  available on the plot helpers.  To break down results by country, use
  ``groupby="country"`` instead.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy.orm import Session, joinedload

from pypsa_app.backend.models import Network, User
from pypsa_app.backend.permissions import can_access
from pypsa_app.backend.services.network import _network_cache
from pypsa_app.backend.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public tool contract
# ---------------------------------------------------------------------------

NAME = "get_network_statistics"

DESCRIPTION = (
    "Get aggregated statistics for a PyPSA energy network. Use this when the "
    "user asks about capacity, costs, energy flows, performance metrics, or "
    "economic results of a network.\n\n"
    "The `category` parameter selects which group of statistics to return:\n"
    "- `overview`: high-level summary (default DataFrame from n.statistics())\n"
    "- `capacity`: installed, optimal, and expanded capacity\n"
    "- `costs`: capex, installed/expanded capex, fom, opex, system cost\n"
    "- `energy`: supply, withdrawal, transmission, energy balance\n"
    "- `performance`: capacity factor, curtailment\n"
    "- `economic`: revenue, market value, prices\n\n"
    "All results are aggregated over time (no raw hourly data). The "
    "groupby_time parameter controls *how* to aggregate over time: sum "
    "(default), mean, max, or min. Some methods (capacity_factor, "
    "market_value) default to 'mean' internally — setting groupby_time "
    "overrides their default.\n\n"
    "The `groupby` parameter controls *what dimension* results are grouped "
    "by: 'carrier' (default, most concise), 'bus', or 'country'. Use "
    "'country' when the user asks about results broken down by geography.\n\n"
    "The `groupby_method` parameter controls *how groups are aggregated*: "
    "'sum' (default), 'mean', 'min', 'max', 'first', or 'last'. For "
    "example, use groupby_method='mean' to get the average across groups "
    "instead of the sum.\n\n"
    "If the network has not been solved, temporal methods return empty "
    "results and a `network_not_solved` warning is included.\n\n"
    "If the network id is unknown or the user lacks access, returns "
    "{error: 'network_not_found'}."
)

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "network_id": {
            "type": "string",
            "description": "UUID of the network. Get ids from list_networks.",
        },
        "category": {
            "type": "string",
            "enum": [
                "overview",
                "capacity",
                "costs",
                "energy",
                "performance",
                "economic",
            ],
            "description": "Which group of statistics to return.",
        },
        "groupby": {
            "type": "string",
            "enum": ["carrier", "bus", "country"],
            "description": (
                "How to group results. 'carrier' (default) groups by energy "
                "type (wind, solar, gas, etc.). 'bus' groups by bus. 'country' "
                "groups by geographic area — use this when the user asks about "
                "results by country or region."
            ),
        },
        "groupby_time": {
            "type": "string",
            "enum": ["sum", "mean", "max", "min"],
            "description": (
                "How to aggregate temporal statistics. Default: each method "
                "uses its PyPSA default (sum for most, mean for capacity_factor "
                "and market_value). Setting this overrides the default. "
                "This always produces a single aggregate value per row — "
                "raw time-series is not available."
            ),
        },
        "groupby_method": {
            "type": "string",
            "enum": ["sum", "mean", "min", "max", "first", "last"],
            "description": (
                "How to aggregate values within the same group. Default: 'sum'. "
                "Use 'mean' to get averages across groups (e.g. mean capacity "
                "per carrier) rather than totals."
            ),
        },
        "carrier": {
            "type": "string",
            "description": "Filter results to a specific carrier name.",
        },
        "bus_carrier": {
            "type": "string",
            "description": "Filter results to a specific bus carrier (e.g. 'AC', 'DC').",
        },
        "nice_names": {
            "type": "boolean",
            "description": "Use human-readable carrier/component names. Default: true.",
        },
    },
    "required": ["network_id", "category"],
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# Category → method mapping
# ---------------------------------------------------------------------------

_METHOD_DEFS: list[dict[str, Any]] = [
    # overview
    dict(category="overview", method="__call__", key="summary",
         strip_kwargs={"groupby_time"}),
    # capacity
    dict(category="capacity", method="installed_capacity", key="installed_capacity"),
    dict(category="capacity", method="optimal_capacity", key="optimal_capacity"),
    dict(category="capacity", method="expanded_capacity", key="expanded_capacity"),
    # costs
    dict(category="costs", method="capex", key="capex"),
    dict(category="costs", method="installed_capex", key="installed_capex"),
    dict(category="costs", method="expanded_capex", key="expanded_capex"),
    dict(category="costs", method="fom", key="fom"),
    dict(category="costs", method="opex", key="opex"),
    dict(category="costs", method="system_cost", key="system_cost"),
    # energy
    dict(category="energy", method="supply", key="supply"),
    dict(category="energy", method="withdrawal", key="withdrawal"),
    dict(category="energy", method="transmission", key="transmission"),
    dict(category="energy", method="energy_balance", key="energy_balance"),
    # performance
    dict(category="performance", method="capacity_factor", key="capacity_factor"),
    dict(category="performance", method="curtailment", key="curtailment"),
    # economic
    dict(category="economic", method="revenue", key="revenue"),
    dict(category="economic", method="market_value", key="market_value"),
    dict(category="economic", method="prices", key="prices",
         strip_kwargs={"nice_names", "groupby_method"}),
]

_CATEGORY_METHODS: dict[str, list[dict[str, Any]]] = {}
for _def in _METHOD_DEFS:
    _CATEGORY_METHODS.setdefault(_def["category"], []).append(_def)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_network(*, db: Session, network_id: UUID) -> Network | None:
    """Fetch the network row from the DB (with owner loaded)."""
    return (
        db.query(Network)
        .options(joinedload(Network.owner))
        .filter(Network.id == network_id)
        .first()
    )


def _load_network(network: Network) -> Any:
    """Load the PyPSA Network object from disk, using the app-wide cache."""
    import pypsa

    file_path = settings.networks_path / network.file_path
    cached = _network_cache.get(file_path)
    if cached is not None:
        return cached
    n = pypsa.Network(file_path)
    _network_cache.put(file_path, n)
    return n


def _flatten_series(data: pd.Series) -> list[dict[str, Any]]:
    """Flatten a Series (possibly MultiIndex) to list[dict].

    Each index level becomes a key, plus ``"value"``.
    NaN values are dropped. Floats are rounded to 2 dp.
    """
    if len(data) == 0:
        return []

    records: list[dict[str, Any]] = []
    if isinstance(data.index, pd.MultiIndex):
        for idx_tup, val in data.items():
            if pd.isna(val):
                continue
            entry: dict[str, Any] = {}
            for i, (name, label) in enumerate(
                zip(data.index.names, tuple(idx_tup), strict=False)  # type: ignore[arg-type]
            ):
                entry[name or f"level_{i}"] = (
                    label if isinstance(label, str) else str(label)
                )
            entry["value"] = round(val, 2) if isinstance(val, float) else val
            records.append(entry)
    else:
        for idx, val in data.items():
            if pd.isna(val):
                continue
            key = data.index.name or "level_0"
            entry = {
                str(key): idx if isinstance(idx, str) else str(idx),
                "value": round(val, 2) if isinstance(val, float) else val,
            }
            records.append(entry)

    return records


def _serialize_overview(
    data: pd.DataFrame, groupby: str = "carrier"
) -> dict[str, list[dict[str, Any]]]:
    """Serialize the overview DataFrame as dict[column → list[dict]].

    The overview DataFrame has unnamed index levels (None, None) —
    we fill them as ("component", *groupby*) so callers get meaningful keys.
    """
    if data.empty:
        return {}

    fallback_names = ("component", groupby)
    idx_names = [
        data.index.names[i] or fallback_names[i]
        if i < len(fallback_names)
        else f"level_{i}"
        for i in range(len(data.index.names))
    ]

    result: dict[str, list[dict[str, Any]]] = {}
    for col in data.columns:
        records: list[dict[str, Any]] = []
        for idx, val in data[col].items():
            if pd.isna(val):
                continue
            entry: dict[str, Any] = {}
            if isinstance(idx, tuple):
                for i, label in enumerate(idx):
                    entry[idx_names[i]] = (
                        label if isinstance(label, str) else str(label)
                    )
            else:
                entry[idx_names[0]] = (
                    idx if isinstance(idx, str) else str(idx)
                )
            entry["value"] = round(val, 2) if isinstance(val, float) else val
            records.append(entry)
        result[str(col)] = records

    return result


def _call_method(
    n: Any,
    method_def: dict[str, Any],
    base_kwargs: dict[str, Any],
) -> pd.Series | pd.DataFrame | None:
    """Call a PyPSA statistics method, stripping kwargs it doesn't accept."""
    stripped = base_kwargs.copy()
    for kw in method_def.get("strip_kwargs", set()):
        stripped.pop(kw, None)

    method_name = method_def["method"]
    if method_name == "__call__":
        return n.statistics(**stripped)

    method = getattr(n.statistics, method_name, None)
    if method is None:
        logger.warning("PyPSA has no statistics method %s", method_name)
        return None
    return method(**stripped)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------


def handler(
    *,
    db: Session,
    user: User,
    network_id: str,
    category: str,
    groupby: str | None = None,
    groupby_time: str | None = None,
    groupby_method: str | None = None,
    carrier: str | None = None,
    bus_carrier: str | None = None,
    nice_names: bool | None = True,
) -> dict[str, Any]:
    """Compute aggregated statistics for a network by category."""
    # --- Validate & authorize ---
    try:
        parsed_id = UUID(str(network_id))
    except (ValueError, TypeError, AttributeError):
        return {"error": "invalid_network_id"}

    network = _resolve_network(db=db, network_id=parsed_id)
    if network is None or not can_access(user, network):
        return {"error": "network_not_found"}

    if nice_names is None:
        nice_names = True

    # --- Validate groupby ---
    _VALID_GROUPBY = {"carrier", "bus", "country"}
    if groupby is not None and groupby not in _VALID_GROUPBY:
        return {"error": "invalid_groupby", "detail": f"groupby must be one of {sorted(_VALID_GROUPBY)}"}

    _VALID_GROUPBY_METHOD = {"sum", "mean", "min", "max", "first", "last"}
    if groupby_method is not None and groupby_method not in _VALID_GROUPBY_METHOD:
        return {"error": "invalid_groupby_method", "detail": f"groupby_method must be one of {sorted(_VALID_GROUPBY_METHOD)}"}

    # --- Load PyPSA network ---
    try:
        n = _load_network(network)
    except Exception as exc:
        logger.exception("Failed to load network %s", parsed_id)
        return {"error": "network_load_failed", "detail": str(exc)}

    # --- Detect unsolved network ---
    warnings: list[str] = []
    if not getattr(n, "is_solved", False):
        warnings.append("network_not_solved")

    # --- Build base kwargs ---
    # Only pass groupby_time when the user explicitly sets it — otherwise
    # each PyPSA method uses its own default (sum for most, mean for
    # capacity_factor and market_value).
    base_kwargs: dict[str, Any] = {"nice_names": nice_names, "round": 2}
    if groupby is not None:
        base_kwargs["groupby"] = groupby
    if groupby_time is not None:
        base_kwargs["groupby_time"] = groupby_time
    if groupby_method is not None:
        base_kwargs["groupby_method"] = groupby_method
    if carrier is not None:
        base_kwargs["carrier"] = carrier
    if bus_carrier is not None:
        base_kwargs["bus_carrier"] = bus_carrier

    # --- Compute statistics ---
    statistics: dict[str, Any] = {}

    for method_def in _CATEGORY_METHODS.get(category, []):
        key = method_def["key"]

        try:
            result = _call_method(n, method_def, base_kwargs)
        except Exception as exc:
            logger.warning("Statistics method %s failed: %s", method_def["method"], exc)
            warnings.append(f"method_{method_def['method']}_failed: {exc!s}")
            continue

        if result is None:
            statistics[key] = []
            continue

        if isinstance(result, pd.DataFrame):
            statistics[key] = _serialize_overview(result, groupby=groupby or "carrier")
        elif isinstance(result, pd.Series):
            statistics[key] = _flatten_series(result)
        else:
            statistics[key] = str(result)

    # --- All-empty check ---
    if all(
        (isinstance(v, list) and len(v) == 0)
        or (isinstance(v, dict) and len(v) == 0)
        for v in statistics.values()
    ):
        if "network_not_solved" not in warnings:
            warnings.append("network_not_solved")

    return {
        "network_id": str(parsed_id),
        "category": category,
        "statistics": statistics,
        "warnings": warnings,
    }