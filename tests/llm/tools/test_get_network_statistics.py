"""Tests for GetNetworkStatisticsTool.

Contract:
- ONE PyPSA stats method per tool call (no `category` enum).
- Tool POSTs to ``/api/v1/statistics/`` (existing async endpoint), polls
  ``/api/v1/tasks/status/{task_id}`` until SUCCESS, then post-processes
  the result on the LLM side.
- ``statistic="summary"`` is accepted as an alias for ``n.statistics()``.
- Output payload carries renderer-friendly ``{summary, data, display_hint}``
  plus rich metadata (``network_id``, ``statistic``, ``units``, ``warnings``).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from pypsa_app.llm.tools.base import ToolContext
from pypsa_app.llm.tools.get_network_statistics import GetNetworkStatisticsTool
from pypsa_app.llm.tools.http_client import cookies_for


def _post_response(task_id: str = "task-abc") -> httpx.Response:
    """Build the response returned when POSTing to /api/v1/statistics/."""
    return httpx.Response(
        status_code=200,
        json={
            "task_id": task_id,
            "status_url": f"/api/v1/tasks/status/{task_id}",
        },
        request=httpx.Request("POST", "http://internal/api/v1/statistics/"),
    )


def _success_status(task_id: str = "task-abc", data: object = None) -> httpx.Response:
    """Build a SUCCESS task-status response wrapping ``data``."""
    return httpx.Response(
        status_code=200,
        json={
            "task_id": task_id,
            "state": "SUCCESS",
            "result": {
                "status": "success",
                "task_id": task_id,
                "data": data if data is not None else {"Solar": 500.0, "Wind": 740.0},
                "request": {"statistic": "capex"},
            },
        },
        request=httpx.Request("GET", f"http://internal/api/v1/tasks/status/{task_id}"),
    )


def _pending_status(task_id: str = "task-abc") -> httpx.Response:
    return httpx.Response(
        status_code=200,
        json={"task_id": task_id, "state": "PENDING", "message": "queued"},
        request=httpx.Request("GET", f"http://internal/api/v1/tasks/status/{task_id}"),
    )


def _failure_status(task_id: str = "task-abc") -> httpx.Response:
    return httpx.Response(
        status_code=200,
        json={
            "task_id": task_id,
            "state": "FAILURE",
            "error": "method 'capex' not available on unsolved network",
        },
        request=httpx.Request("GET", f"http://internal/api/v1/tasks/status/{task_id}"),
    )


class TestGetNetworkStatisticsToolSchema:
    """The tool advertises a one-method-per-call schema."""

    def test_parameters_schema_has_statistic_enum_no_category(self) -> None:
        tool = GetNetworkStatisticsTool(http=AsyncMock(spec=httpx.AsyncClient))
        schema = tool.parameters_schema
        properties = schema["properties"]

        assert "statistic" in properties, (
            "parameters_schema must expose a 'statistic' field"
        )
        assert "category" not in properties, (
            "parameters_schema must NOT expose 'category' — design dropped fan-out"
        )
        # statistic is a closed enum so the LLM can only pick allowed methods.
        assert "enum" in properties["statistic"]
        # Required fields cover the minimum to make a call.
        assert set(schema["required"]) == {"network_id", "statistic"}

    def test_statistic_enum_includes_summary_and_fom(self) -> None:
        """The 'summary' alias and 'fom' must both be
        offered to the LLM."""
        tool = GetNetworkStatisticsTool(http=AsyncMock(spec=httpx.AsyncClient))
        enum = set(tool.parameters_schema["properties"]["statistic"]["enum"])
        assert "summary" in enum
        assert "fom" in enum
        assert "capex" in enum  # sanity


class TestGetNetworkStatisticsToolInvoke:
    """The tool drives the existing async statistics endpoint end-to-end."""

    @pytest.mark.anyio
    async def test_invoke_posts_to_async_statistics_endpoint(self) -> None:
        """The tool POSTs to /api/v1/statistics/ with network_ids, statistic,
        and a parameters dict — matching the existing endpoint contract."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response())
        mock_http.get = AsyncMock(return_value=_success_status())

        tool = GetNetworkStatisticsTool(http=mock_http)
        ctx = ToolContext(user_id="u1", auth_cookie=None)
        await tool.invoke({"network_id": "n1", "statistic": "capex"}, ctx)

        mock_http.post.assert_awaited_once()
        call_args = mock_http.post.await_args
        assert call_args.args[0] == "/api/v1/statistics/"
        body = call_args.kwargs["json"]
        assert body == {
            "network_ids": ["n1"],
            "statistic": "capex",
            "parameters": {},
        }

    @pytest.mark.anyio
    async def test_invoke_polls_task_status_until_success(self) -> None:
        """The tool polls /api/v1/tasks/status/{task_id} after queueing the task."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response("task-xyz"))
        mock_http.get = AsyncMock(return_value=_success_status("task-xyz"))

        tool = GetNetworkStatisticsTool(http=mock_http)
        ctx = ToolContext(user_id="u1", auth_cookie=None)
        await tool.invoke({"network_id": "n1", "statistic": "capex"}, ctx)

        mock_http.get.assert_awaited()
        get_url = mock_http.get.await_args.args[0]
        assert get_url == "/api/v1/tasks/status/task-xyz"

    @pytest.mark.anyio
    async def test_invoke_polls_through_pending_state(self) -> None:
        """When the first poll returns PENDING, the tool keeps polling until
        a terminal state appears."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response())
        mock_http.get = AsyncMock(
            side_effect=[_pending_status(), _pending_status(), _success_status()]
        )

        tool = GetNetworkStatisticsTool(http=mock_http)
        # Skip real waits in tests.
        tool.poll_interval_seconds = 0.0
        ctx = ToolContext(user_id="u1", auth_cookie=None)
        result = await tool.invoke({"network_id": "n1", "statistic": "capex"}, ctx)

        assert result.is_error is False
        assert mock_http.get.await_count == 3

    @pytest.mark.anyio
    async def test_invoke_returns_error_on_task_failure(self) -> None:
        """When the task state is FAILURE, the tool returns is_error=True with
        the backend's error message."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response())
        mock_http.get = AsyncMock(return_value=_failure_status())

        tool = GetNetworkStatisticsTool(http=mock_http)
        tool.poll_interval_seconds = 0.0
        ctx = ToolContext(user_id="u1", auth_cookie=None)
        result = await tool.invoke({"network_id": "n1", "statistic": "capex"}, ctx)

        assert result.is_error is True
        assert result.error is not None
        assert "capex" in result.error or "unsolved" in result.error

    @pytest.mark.anyio
    async def test_invoke_forwards_auth_cookie_on_post_and_get(self) -> None:
        """The tool forwards the auth cookie via cookies_for(ctx) on both
        POST and GET so per-user permission checks apply on every request."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response())
        mock_http.get = AsyncMock(return_value=_success_status())

        tool = GetNetworkStatisticsTool(http=mock_http)
        ctx = ToolContext(user_id="u1", auth_cookie="abc123")

        await tool.invoke({"network_id": "n1", "statistic": "capex"}, ctx)

        expected = cookies_for(ctx)
        assert mock_http.post.await_args.kwargs["cookies"] == expected
        assert mock_http.get.await_args.kwargs["cookies"] == expected

    @pytest.mark.anyio
    async def test_invoke_forwards_optional_parameters(self) -> None:
        """groupby, groupby_time, groupby_method, carrier, bus_carrier,
        nice_names — when provided, all flow into the parameters dict in the
        POST body."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response())
        mock_http.get = AsyncMock(return_value=_success_status())

        tool = GetNetworkStatisticsTool(http=mock_http)
        ctx = ToolContext(user_id="u1", auth_cookie=None)
        await tool.invoke(
            {
                "network_id": "n1",
                "statistic": "supply",
                "groupby": "carrier",
                "groupby_time": "sum",
                "groupby_method": "sum",
                "carrier": "solar",
                "bus_carrier": "AC",
                "nice_names": True,
            },
            ctx,
        )

        body = mock_http.post.await_args.kwargs["json"]
        assert body["parameters"] == {
            "groupby": "carrier",
            "groupby_time": "sum",
            "groupby_method": "sum",
            "carrier": "solar",
            "bus_carrier": "AC",
            "nice_names": True,
        }

    @pytest.mark.anyio
    async def test_invoke_payload_includes_units_for_statistic(self) -> None:
        """Payload carries a 'units' string the LLM can quote in its reply.
        Units come from the LLM-side mapping, not the backend."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response())
        mock_http.get = AsyncMock(return_value=_success_status())

        tool = GetNetworkStatisticsTool(http=mock_http)
        ctx = ToolContext(user_id="u1", auth_cookie=None)
        result = await tool.invoke({"network_id": "n1", "statistic": "capex"}, ctx)

        assert result.is_error is False
        assert result.payload is not None
        assert "units" in result.payload
        assert result.payload["units"] == "currency (typically EUR)"

    @pytest.mark.anyio
    async def test_invoke_payload_includes_statistic_and_network_id(self) -> None:
        """Payload echoes the statistic name and network id for downstream
        consumers (LLM context, renderer)."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response())
        mock_http.get = AsyncMock(return_value=_success_status())

        tool = GetNetworkStatisticsTool(http=mock_http)
        ctx = ToolContext(user_id="u1", auth_cookie=None)
        result = await tool.invoke({"network_id": "n1", "statistic": "capex"}, ctx)

        assert result.payload["network_id"] == "n1"
        assert result.payload["statistic"] == "capex"

    @pytest.mark.anyio
    async def test_invoke_handles_summary_statistic(self) -> None:
        """statistic='summary' is accepted; it routes to n.statistics() via the
        backend's special case (we just verify the tool passes it through)."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response())
        mock_http.get = AsyncMock(
            return_value=_success_status(
                data={
                    "index": ["Generator"],
                    "columns": ["Capacity"],
                    "data": [[1000.0]],
                }
            )
        )

        tool = GetNetworkStatisticsTool(http=mock_http)
        ctx = ToolContext(user_id="u1", auth_cookie=None)
        result = await tool.invoke({"network_id": "n1", "statistic": "summary"}, ctx)

        # POST forwards 'summary' verbatim.
        assert mock_http.post.await_args.kwargs["json"]["statistic"] == "summary"
        assert result.is_error is False
        assert result.payload["statistic"] == "summary"

    @pytest.mark.anyio
    async def test_invoke_payload_renders_series_as_table_data(self) -> None:
        """For Series-shaped backend data ({key: value}), the tool exposes
        renderer-friendly data.columns / data.rows."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response())
        mock_http.get = AsyncMock(
            return_value=_success_status(data={"Solar": 500.0, "Wind": 740.0})
        )

        tool = GetNetworkStatisticsTool(http=mock_http)
        ctx = ToolContext(user_id="u1", auth_cookie=None)
        result = await tool.invoke({"network_id": "n1", "statistic": "capex"}, ctx)

        data = result.payload["data"]
        assert data["columns"] == ["index", "value"]
        assert sorted(data["rows"]) == sorted([["Solar", 500.0], ["Wind", 740.0]])
        assert result.payload["display_hint"] == "table"

    @pytest.mark.anyio
    async def test_invoke_payload_renders_dataframe_as_table_data(self) -> None:
        """For DataFrame-shaped backend data (split format), the tool exposes
        renderer-friendly data.columns / data.rows."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response())
        mock_http.get = AsyncMock(
            return_value=_success_status(
                data={
                    "index": ["Generator", "Link"],
                    "columns": ["Capacity"],
                    "data": [[1000.0], [200.0]],
                }
            )
        )

        tool = GetNetworkStatisticsTool(http=mock_http)
        ctx = ToolContext(user_id="u1", auth_cookie=None)
        result = await tool.invoke({"network_id": "n1", "statistic": "summary"}, ctx)

        data = result.payload["data"]
        assert data["columns"] == ["index", "Capacity"]
        assert data["rows"] == [["Generator", 1000.0], ["Link", 200.0]]

    @pytest.mark.anyio
    async def test_invoke_emits_network_not_solved_warning_when_data_empty(
        self,
    ) -> None:
        """An empty result for time-dependent stats (e.g. capacity_factor)
        means the network wasn't optimised — surface that as a warning so the
        LLM can mention it."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response())
        mock_http.get = AsyncMock(return_value=_success_status(data={}))

        tool = GetNetworkStatisticsTool(http=mock_http)
        ctx = ToolContext(user_id="u1", auth_cookie=None)
        result = await tool.invoke(
            {"network_id": "n1", "statistic": "capacity_factor"}, ctx
        )

        assert "network_not_solved" in result.payload["warnings"]

    @pytest.mark.anyio
    async def test_invoke_returns_summary_text_referencing_statistic(
        self,
    ) -> None:
        """The renderer shows result.summary as plain text — the tool composes
        a short human-readable string."""
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_post_response())
        mock_http.get = AsyncMock(return_value=_success_status())

        tool = GetNetworkStatisticsTool(http=mock_http)
        ctx = ToolContext(user_id="u1", auth_cookie=None)
        result = await tool.invoke({"network_id": "n1", "statistic": "capex"}, ctx)

        assert isinstance(result.payload["summary"], str)
        assert "capex" in result.payload["summary"].lower()
