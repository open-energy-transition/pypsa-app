"""Tests for backend.services.statistics.get_statistics.

When ``statistic == "summary"``, the service must call
``n.statistics(**parameters)`` (the ``__call__`` of the statistics accessor)
rather than ``getattr(n.statistics, "summary")``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from pypsa_app.backend.services.statistics import get_statistics


class TestGetStatisticsSummary:
    """``summary`` is the user-facing alias for ``n.statistics()``."""

    def test_summary_invokes_statistics_callable_with_parameters(self) -> None:
        """statistic='summary' must call n.statistics(**parameters), not
        getattr(n.statistics, 'summary')."""
        fake_df = pd.DataFrame({"v": [1.0, 2.0]}, index=["a", "b"])
        statistics_callable = MagicMock(return_value=fake_df)
        # The PyPSA statistics accessor is callable; statistic='summary' must
        # invoke that callable rather than look up an attribute named 'summary'.
        fake_n = MagicMock()
        fake_n.statistics = statistics_callable
        fake_service = MagicMock(n=fake_n)

        with patch(
            "pypsa_app.backend.services.statistics.load_service",
            return_value=fake_service,
        ):
            result = get_statistics(
                ["/tmp/x.nc"],
                "summary",
                {"groupby": "carrier", "nice_names": True},
            )

        statistics_callable.assert_called_once_with(groupby="carrier", nice_names=True)
        assert isinstance(result, dict)

    def test_named_method_still_uses_getattr(self) -> None:
        """statistic != 'summary' must use getattr(n.statistics, statistic)."""
        fake_df = pd.DataFrame({"v": [3.0]}, index=["x"])
        capex_method = MagicMock(return_value=fake_df)
        fake_n = MagicMock()
        # n.statistics.capex(...) is the named-method path.
        fake_n.statistics.capex = capex_method
        fake_service = MagicMock(n=fake_n)

        with patch(
            "pypsa_app.backend.services.statistics.load_service",
            return_value=fake_service,
        ):
            get_statistics(["/tmp/x.nc"], "capex", {"groupby": "bus"})

        capex_method.assert_called_once_with(groupby="bus")
