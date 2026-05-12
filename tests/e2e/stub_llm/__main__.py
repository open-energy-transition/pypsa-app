"""Entry point for running the stub-LLM as a standalone ASGI server.

Usage::

    python -m tests.e2e.stub_llm

Set ``STUB_LLM_PORT`` env var to change port (default 8001).
"""

from __future__ import annotations

import os

import uvicorn

from tests.e2e.stub_llm.app import app

PORT = int(os.environ.get("STUB_LLM_PORT", "8001"))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
