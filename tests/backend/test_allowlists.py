"""Tests for backend.utils.allowlists."""

from __future__ import annotations

from pypsa_app.backend.utils.allowlists import ALLOWED_STATISTICS


class TestAllowedStatistics:
    def test_fom_is_allowed(self) -> None:
        """``fom`` (fixed O&M cost) must be allowlisted for POST /api/v1/statistics/."""
        assert "fom" in ALLOWED_STATISTICS
