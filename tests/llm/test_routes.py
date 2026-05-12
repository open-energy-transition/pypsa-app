"""Tests for POST /api/v1/chat/stream and GET /api/v1/chat/health routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from pypsa_app.llm.api.schemas import ChatContext, ChatMessage, ChatRequest


class TestChatStreamRoute:
    """Unit tests for the chat_stream route handler.

    Calls the handler directly with mocked dependencies to verify
    the contract without requiring a running server.
    """

    @pytest.fixture
    def chat_request(self) -> ChatRequest:
        return ChatRequest(
            messages=[
                ChatMessage(
                    id="msg-1",
                    role="user",
                    content="Hi",
                    timestamp="2026-05-05T10:00:00Z",
                )
            ],
            context=ChatContext(),
        )

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        mock = MagicMock(spec=Request)
        mock.is_disconnected = AsyncMock(return_value=False)
        return mock

    @pytest.fixture
    def mock_user(self) -> MagicMock:
        mock = MagicMock()
        mock.id = "user-1"
        return mock

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        mock = MagicMock()

        async def fake_run_chat(**kwargs: object) -> object:
            yield (
                b'event: RunStarted\n'
                b'data:{"run_id":"run_abc","model":"test"}\n\n'
            )
            yield (
                b'event: TextMessageContent\n'
                b'data:{"message_id":"msg_1","delta":"Hi"}\n\n'
            )
            yield (
                b'event: RunFinished\n'
                b'data:{"run_id":"run_abc","usage":'
                b'{"input_tokens":0,"output_tokens":0},'
                b'"stop_reason":"end_turn"}\n\n'
            )

        mock.run_chat = fake_run_chat
        mock.health = AsyncMock(
            return_value={"ok": True, "model": "test"}
        )
        return mock

    @pytest.mark.anyio
    async def test_handler_returned_by_routes_module(
        self,
    ) -> None:
        """The routes module must expose a callable chat_stream handler."""
        from pypsa_app.llm.api import routes

        assert hasattr(routes, "chat_stream")
        assert callable(routes.chat_stream)

    @pytest.mark.anyio
    async def test_returns_streaming_response_with_sse_media_type(
        self,
        chat_request: ChatRequest,
        mock_request: MagicMock,
        mock_user: MagicMock,
        mock_service: MagicMock,
    ) -> None:
        """chat_stream must return a StreamingResponse with
        media_type 'text/event-stream'."""
        from pypsa_app.llm.api.routes import chat_stream

        response = await chat_stream(
            body=chat_request,
            request=mock_request,
            user=mock_user,
            service=mock_service,
        )

        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"

    @pytest.mark.anyio
    async def test_sets_correct_sse_headers(
        self,
        chat_request: ChatRequest,
        mock_request: MagicMock,
        mock_user: MagicMock,
        mock_service: MagicMock,
    ) -> None:
        """chat_stream must set Cache-Control, X-Accel-Buffering, and Connection headers."""
        from pypsa_app.llm.api.routes import chat_stream

        response = await chat_stream(
            body=chat_request,
            request=mock_request,
            user=mock_user,
            service=mock_service,
        )

        headers = response.headers
        assert headers.get("Cache-Control") == "no-cache, no-transform"
        assert headers.get("X-Accel-Buffering") == "no"
        assert headers.get("Connection") == "keep-alive"

    @pytest.mark.anyio
    async def test_streams_sse_bytes_from_service_run_chat(
        self,
        chat_request: ChatRequest,
        mock_request: MagicMock,
        mock_user: MagicMock,
        mock_service: MagicMock,
    ) -> None:
        """chat_stream must yield SSE bytes produced by
        service.run_chat."""
        from pypsa_app.llm.api.routes import chat_stream

        response = await chat_stream(
            body=chat_request,
            request=mock_request,
            user=mock_user,
            service=mock_service,
        )

        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk

        assert b"RunStarted" in body_bytes
        assert b"TextMessageContent" in body_bytes
        assert b"RunFinished" in body_bytes

    @pytest.mark.anyio
    async def test_passes_correct_params_to_service_run_chat(
        self,
        chat_request: ChatRequest,
        mock_request: MagicMock,
        mock_user: MagicMock,
        mock_service: MagicMock,
    ) -> None:
        """chat_stream must pass user, messages, context, and client_disconnected to service.run_chat."""
        from pypsa_app.llm.api.routes import chat_stream

        called_kwargs: dict[str, object] = {}

        async def recording_run_chat(**kwargs: object) -> object:
            called_kwargs.update(kwargs)
            yield (
                b'event: RunStarted\n'
                b'data:{"run_id":"run_abc","model":"test"}\n\n'
            )
            yield (
                b'event: RunFinished\n'
                b'data:{"run_id":"run_abc","usage":'
                b'{"input_tokens":0,"output_tokens":0},'
                b'"stop_reason":"end_turn"}\n\n'
            )

        mock_service.run_chat = recording_run_chat

        response = await chat_stream(
            body=chat_request,
            request=mock_request,
            user=mock_user,
            service=mock_service,
        )

        # Consume the stream
        async for _ in response.body_iterator:
            pass

        assert called_kwargs["user"] == mock_user
        assert called_kwargs["messages"] == chat_request.messages
        assert called_kwargs["context"] == chat_request.context
        assert callable(called_kwargs["client_disconnected"])
        # The client_disconnected callable must be the request's
        # is_disconnected method bound to the mock_request
        assert await called_kwargs["client_disconnected"]() is False

    @pytest.mark.anyio
    async def test_forwards_auth_cookie_from_request_to_service(
        self,
        chat_request: ChatRequest,
        mock_user: MagicMock,
        mock_service: MagicMock,
    ) -> None:
        """chat_stream must extract the SESSION_COOKIE_NAME ('pypsa_session')
        cookie from the request and pass it as auth_cookie to
        service.run_chat.
        """
        from pypsa_app.llm.api.routes import chat_stream

        mock_request = MagicMock(spec=Request)
        mock_request.is_disconnected = AsyncMock(return_value=False)
        mock_request.cookies = {"pypsa_session": "session_xyz"}

        called_kwargs: dict[str, object] = {}

        async def recording_run_chat(**kwargs: object) -> object:
            called_kwargs.update(kwargs)
            yield (
                b'event: RunStarted\n'
                b'data:{"run_id":"run_abc","model":"test"}\n\n'
            )
            yield (
                b'event: RunFinished\n'
                b'data:{"run_id":"run_abc","usage":'
                b'{"input_tokens":0,"output_tokens":0},'
                b'"stop_reason":"end_turn"}\n\n'
            )

        mock_service.run_chat = recording_run_chat

        response = await chat_stream(
            body=chat_request,
            request=mock_request,
            user=mock_user,
            service=mock_service,
        )

        async for _ in response.body_iterator:
            pass

        assert called_kwargs["auth_cookie"] == "session_xyz", (
            f"Expected auth_cookie='session_xyz', "
            f"got {called_kwargs.get('auth_cookie')!r}"
        )

    @pytest.mark.anyio
    async def test_handler_is_registered_on_router(
        self,
    ) -> None:
        """The chat_stream handler must be registered on the
        llm router as a POST /chat/stream route."""
        from pypsa_app.llm.api.routes import router

        route_paths = [r.path for r in router.routes]
        assert "/chat/stream" in route_paths, (
            f"Expected /chat/stream in router paths, got {route_paths}"
        )

        # Find the specific route and verify it's POST
        stream_routes = [
            r for r in router.routes if r.path == "/chat/stream"
        ]
        assert len(stream_routes) == 1
        assert "POST" in stream_routes[0].methods


class TestChatHealthRoute:
    """Unit tests for the chat_health route handler."""

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        mock = MagicMock()
        mock.health = AsyncMock(
            return_value={"ok": True, "model": "test-model"}
        )
        return mock

    @pytest.mark.anyio
    async def test_handler_returned_by_routes_module(
        self,
    ) -> None:
        """The routes module must expose a callable chat_health handler."""
        from pypsa_app.llm.api import routes

        assert hasattr(routes, "chat_health")
        assert callable(routes.chat_health)

    @pytest.mark.anyio
    async def test_delegates_to_service_health(
        self, mock_service: MagicMock
    ) -> None:
        """chat_health must delegate to service.health() and return the result dict."""
        from pypsa_app.llm.api.routes import chat_health

        result = await chat_health(service=mock_service)

        assert result == {"ok": True, "model": "test-model"}
        mock_service.health.assert_awaited_once()

    @pytest.mark.anyio
    async def test_handler_is_registered_on_router(
        self,
    ) -> None:
        """The chat_health handler must be registered on the
        llm router as a GET /chat/health route."""
        from pypsa_app.llm.api.routes import router

        route_paths = [r.path for r in router.routes]
        assert "/chat/health" in route_paths, (
            f"Expected /chat/health in router paths, got {route_paths}"
        )

        health_routes = [
            r for r in router.routes if r.path == "/chat/health"
        ]
        assert len(health_routes) == 1
        assert "GET" in health_routes[0].methods


class TestChatHealthRouteIntegration:
    """HTTP integration tests for GET /api/v1/chat/health via TestClient.

    Verifies that the health route functions correctly through the full
    FastAPI dependency-injection stack. Complements the direct-handler
    tests in ``TestChatHealthRoute`` by exercising the wire protocol.
    """

    @pytest.fixture(autouse=True)
    def clear_overrides(self) -> None:
        """Ensure dependency_overrides are clean before and after each test."""
        from pypsa_app.backend.main import app

        app.dependency_overrides.clear()
        yield
        app.dependency_overrides.clear()

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        mock = MagicMock()
        mock.health = AsyncMock(
            return_value={"ok": True, "model": "openai/qwen3.5:9b"}
        )
        return mock

    @pytest.mark.anyio
    async def test_returns_200_and_health_payload_when_enabled(
        self, mock_service: MagicMock
    ) -> None:
        """GET /api/v1/chat/health must return 200 with
        ``{"ok": true, "model": "..."}`` when chat is enabled."""
        from pypsa_app.backend.main import app
        from pypsa_app.llm.api.deps import (
            get_chat_service as real_get_chat_service,
        )
        from pypsa_app.llm.api.deps import (
            require_chat_enabled as real_require_chat_enabled,
        )

        app.dependency_overrides[real_require_chat_enabled] = lambda: None
        app.dependency_overrides[real_get_chat_service] = lambda: mock_service

        client = TestClient(app)
        response = client.get("/api/v1/chat/health")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}"
        )
        body = response.json()
        assert body == {"ok": True, "model": "openai/qwen3.5:9b"}

    @pytest.mark.anyio
    async def test_returns_404_when_chat_disabled(
        self,
    ) -> None:
        """GET /api/v1/chat/health must return 404 when chat is disabled
        (require_chat_enabled raises)."""
        from fastapi import HTTPException, status

        from pypsa_app.backend.main import app
        from pypsa_app.llm.api.deps import (
            require_chat_enabled as real_require_chat_enabled,
        )

        def _chat_disabled() -> None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="chat is disabled",
            )

        app.dependency_overrides[real_require_chat_enabled] = _chat_disabled

        client = TestClient(app)
        response = client.get("/api/v1/chat/health")

        assert response.status_code == 404, (
            f"Expected 404, got {response.status_code}"
        )
        assert response.json()["detail"] == "chat is disabled"

    @pytest.mark.anyio
    async def test_health_route_access_with_fastapi_openapi_schema(
        self, mock_service: MagicMock
    ) -> None:
        """The health route must appear in the OpenAPI schema under the
        /api/v1/chat/health path as a GET operation."""
        from pypsa_app.backend.main import app
        from pypsa_app.llm.api.deps import (
            get_chat_service as real_get_chat_service,
        )
        from pypsa_app.llm.api.deps import (
            require_chat_enabled as real_require_chat_enabled,
        )

        app.dependency_overrides[real_require_chat_enabled] = lambda: None
        app.dependency_overrides[real_get_chat_service] = lambda: mock_service

        openapi = app.openapi()
        paths = openapi.get("paths", {})
        chat_health_path = "/api/v1/chat/health"

        assert chat_health_path in paths, (
            f"Expected {chat_health_path} in OpenAPI paths, "
            f"got {list(paths.keys())}"
        )
        path_op = paths[chat_health_path]
        assert "get" in path_op, (
            f"Expected GET operation on {chat_health_path}, "
            f"got {list(path_op.keys())}"
        )


class TestChatStreamCancellation:
    """Cancellation semantics when the client disconnects."""

    @pytest.fixture
    def chat_request(self) -> ChatRequest:
        return ChatRequest(
            messages=[
                ChatMessage(
                    id="msg-1",
                    role="user",
                    content="Hi",
                    timestamp="2026-05-05T10:00:00Z",
                )
            ],
            context=ChatContext(),
        )

    @pytest.fixture
    def mock_request(self) -> MagicMock:
        mock = MagicMock(spec=Request)
        mock.is_disconnected = AsyncMock(return_value=False)
        return mock

    @pytest.fixture
    def mock_user(self) -> MagicMock:
        mock = MagicMock()
        mock.id = "user-1"
        return mock

    @pytest.fixture
    def mock_service_cancelled(self) -> MagicMock:
        import asyncio

        mock = MagicMock()

        async def failing_run_chat(**kwargs: object) -> object:
            raise asyncio.CancelledError("client disconnect")
            yield  # pragma: no cover

        mock.run_chat = failing_run_chat
        mock.health = AsyncMock(return_value={"ok": True})
        return mock

    @pytest.mark.anyio
    async def test_cancelled_error_logs_and_re_raises(
        self,
        chat_request: ChatRequest,
        mock_request: MagicMock,
        mock_user: MagicMock,
        mock_service_cancelled: MagicMock,
    ) -> None:
        """When the stream is cancelled (client disconnects), the handler must re-raise asyncio.CancelledError."""
        import asyncio

        from pypsa_app.llm.api.routes import chat_stream

        response = await chat_stream(
            body=chat_request,
            request=mock_request,
            user=mock_user,
            service=mock_service_cancelled,
        )

        with pytest.raises(asyncio.CancelledError):
            async for _ in response.body_iterator:
                pass

    @pytest.mark.anyio
    async def test_route_detects_disconnect_via_is_disconnected(
        self,
        chat_request: ChatRequest,
        mock_user: MagicMock,
    ) -> None:
        """The route must check request.is_disconnected() after each yield and cleanly exit the generator when the client disconnects."""
        from pypsa_app.llm.api.routes import chat_stream

        mock_request = MagicMock(spec=Request)
        # Start connected, then become disconnected after first yield
        flag: list[bool] = [False]

        async def is_disconnected() -> bool:
            return flag[0]

        mock_request.is_disconnected = is_disconnected
        mock_request.cookies = {}

        mock_service = MagicMock()

        async def yielding_run_chat(**kwargs: object) -> object:
            yield b'event: RunStarted\ndata:{"run_id":"r1"}\n\n'
            yield (
                b'event: TextMessageContent\n'
                b'data:{"delta":"Hi"}\n\n'
            )
            # The route checks is_disconnected after the first yield
            # and should detect the disconnect -> return (clean exit)
            yield b'event: RunFinished\ndata:{}\n\n'  # pragma: no cover

        mock_service.run_chat = yielding_run_chat
        mock_service.health = AsyncMock(return_value={"ok": True})

        response = await chat_stream(
            body=chat_request,
            request=mock_request,
            user=mock_user,
            service=mock_service,
        )

        # Consume first chunk, then simulate disconnect
        iterator = response.body_iterator.__aiter__()
        await iterator.__anext__()  # Consume RunStarted

        # Now simulate client disconnect
        flag[0] = True

        # The next iteration should detect disconnect and cleanly exit
        # (StopAsyncIteration raised when generator returns)
        with pytest.raises(StopAsyncIteration):
            await iterator.__anext__()


class TestChatStreamSSEHeadersIntegration:
    """Integration tests for SSE response headers via TestClient.

    Verifies that the actual HTTP response from FastAPI includes the
    required SSE headers.
    """

    @pytest.fixture(autouse=True)
    def clear_overrides(self) -> None:
        """Ensure dependency_overrides are clean before and after each test."""
        from pypsa_app.backend.main import app

        app.dependency_overrides.clear()
        yield
        app.dependency_overrides.clear()

    @pytest.fixture
    def mock_user(self) -> MagicMock:
        mock = MagicMock()
        mock.id = "user-1"
        mock.username = "testuser"
        return mock

    @pytest.fixture
    def mock_service(self) -> MagicMock:
        mock = MagicMock()

        async def fake_run_chat(**kwargs: object) -> object:
            yield (
                b'event: RunStarted\n'
                b'data:{"run_id":"run_abc","model":"test"}\n\n'
            )
            yield (
                b'event: RunFinished\n'
                b'data:{"run_id":"run_abc","usage":'
                b'{"input_tokens":10,"output_tokens":5},'
                b'"stop_reason":"end_turn"}\n\n'
            )

        mock.run_chat = fake_run_chat
        mock.health = AsyncMock(return_value={"ok": True})
        return mock

    @pytest.mark.anyio
    async def test_response_includes_sse_headers_via_http(
        self,
        mock_user: MagicMock,
        mock_service: MagicMock,
    ) -> None:
        """The HTTP response must include Cache-Control, X-Accel-Buffering,
        Connection headers and Content-Type text/event-stream when
        accessed via TestClient."""
        from pypsa_app.backend.api.deps import get_active_user as real_get_active_user
        from pypsa_app.backend.main import app
        from pypsa_app.llm.api.deps import (
            get_chat_service as real_get_chat_service,
        )
        from pypsa_app.llm.api.deps import (
            require_chat_enabled as real_require_chat_enabled,
        )

        app.dependency_overrides[real_get_active_user] = lambda: mock_user
        app.dependency_overrides[real_require_chat_enabled] = lambda: None
        app.dependency_overrides[real_get_chat_service] = lambda: mock_service

        client = TestClient(app)
        response = client.post(
            "/api/v1/chat/stream",
            json={
                "messages": [
                    {
                        "id": "msg-1",
                        "role": "user",
                        "content": "Hi",
                        "timestamp": "2026-05-05T10:00:00Z",
                    }
                ],
                "context": {},
            },
        )

        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "text/event-stream" in content_type, (
            f"Expected text/event-stream in content-type, got {content_type}"
        )
        assert response.headers.get("cache-control") == (
            "no-cache, no-transform"
        ), (
            f"Unexpected cache-control: {response.headers.get('cache-control')}"
        )
        assert response.headers.get("x-accel-buffering") == "no", (
            f"Unexpected x-accel-buffering: {response.headers.get('x-accel-buffering')}"
        )
        assert response.headers.get("connection") == "keep-alive", (
            f"Unexpected connection: {response.headers.get('connection')}"
        )
