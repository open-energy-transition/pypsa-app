"""Tests verifying that llm_router is registered on the FastAPI app."""

from __future__ import annotations

from pypsa_app.backend.main import app


class TestLlmRouterRegistration:
    """Verify the llm_router is registered on the FastAPI app."""

    def test_app_includes_chat_stream_route(self) -> None:
        """The FastAPI app must include a POST /api/v1/chat/stream route."""
        chat_routes = {
            r.path: r.methods for r in app.routes if r.path.startswith("/api/v1/chat")
        }
        msg = (
            f"Expected /api/v1/chat/stream in app routes, "
            f"got {list(chat_routes.keys())}"
        )
        assert "/api/v1/chat/stream" in chat_routes, msg
        assert "POST" in chat_routes["/api/v1/chat/stream"], (
            "chat/stream route must accept POST"
        )

    def test_app_includes_chat_health_route(self) -> None:
        """The FastAPI app must include a GET /api/v1/chat/health route."""
        chat_routes = {
            r.path: r.methods for r in app.routes if r.path.startswith("/api/v1/chat")
        }
        msg = (
            f"Expected /api/v1/chat/health in app routes, "
            f"got {list(chat_routes.keys())}"
        )
        assert "/api/v1/chat/health" in chat_routes, msg
        assert "GET" in chat_routes["/api/v1/chat/health"], (
            "chat/health route must accept GET"
        )

    def test_module_imports_llm_router(self) -> None:
        """main.py must import the router from pypsa_app.llm.api.routes."""
        import pypsa_app.backend.main as main_module

        assert hasattr(main_module, "llm_router"), (
            "main.py must import llm_router at module level"
        )
