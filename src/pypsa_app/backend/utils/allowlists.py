"""Security allowlists for PyPSA API inputs to prevent arbitrary code execution"""

from typing import Final

ALLOWED_STATISTICS: Final[frozenset[str]] = frozenset(
    {
        "capex",
        "installed_capex",
        "expanded_capex",
        "fom",
        "opex",
        "system_cost",
        "revenue",
        "market_value",
        "installed_capacity",
        "expanded_capacity",
        "optimal_capacity",
        "supply",
        "withdrawal",
        "curtailment",
        "capacity_factor",
        "transmission",
        "energy_balance",
        "prices",
    }
)

ALLOWED_CHART_TYPES: Final[frozenset[str]] = frozenset(
    {
        "area",
        "bar",
        "map",
        "scatter",
        "line",
        "box",
        "violin",
        "histogram",
    }
)

__all__ = ["ALLOWED_STATISTICS", "ALLOWED_CHART_TYPES"]
