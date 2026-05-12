"""Stub-LLM FastAPI app.

A lightweight ASGI app mimicking an OpenAI-compatible
/v1/chat/completions endpoint that returns scripted SSE streams.
Used by E2E tests when no live LLM is available.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI(title="stub-llm", version="0.1.0")

STUB_MODEL = "stub/qwen3.5:9b"
STUB_CHUNK_ID_BASE = "chatcmpl-stub"

# Scripted assistant response text, split into tokens
SCRIPTED_TOKENS = [
    "Hello! ",
    "I'm ",
    "a ",
    "stub ",
    "LLM ",
    "assistant. ",
    "How ",
    "can ",
    "I ",
    "help ",
    "you ",
    "today?",
]


STUB_TOOL_CALL_ID = "call_stub_list_networks"


def _is_list_networks_request(messages: list[dict]) -> bool:
    """Check if the last user message is a request to list networks."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content") or ""
            return "list networks" in content.lower()
    return False


async def _generate_tool_call_sse_stream(
    request_id: str, model: str
) -> AsyncGenerator[bytes]:
    """Yield OpenAI-compatible SSE chunks with a scripted tool call."""
    created = int(time.time())
    tool_call_id = f"{STUB_TOOL_CALL_ID}-{request_id}"

    # First chunk: tool call start with id, type, function name
    chunk = {
        "id": f"{STUB_CHUNK_ID_BASE}-{request_id}",
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": tool_call_id,
                            "type": "function",
                            "function": {"name": "list_networks", "arguments": ""},
                        }
                    ]
                },
                "finish_reason": None,
            }
        ],
    }
    yield f"data: {json.dumps(chunk)}\n\n".encode()
    await asyncio.sleep(0.01)

    # Argument chunk
    args = '{"limit": 10, "offset": 0}'
    chunk = {
        "id": f"{STUB_CHUNK_ID_BASE}-{request_id}",
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "function": {"arguments": args},
                        }
                    ]
                },
                "finish_reason": None,
            }
        ],
    }
    yield f"data: {json.dumps(chunk)}\n\n".encode()
    await asyncio.sleep(0.01)

    # Final chunk with finish_reason
    final_chunk = {
        "id": f"{STUB_CHUNK_ID_BASE}-{request_id}",
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "tool_calls",
            }
        ],
    }
    yield f"data: {json.dumps(final_chunk)}\n\n".encode()

    # [DONE] sentinel
    yield b"data: [DONE]\n\n"


async def _generate_sse_stream(
    request_id: str, model: str
) -> AsyncGenerator[bytes]:
    """Yield OpenAI-compatible SSE chunks for a scripted response."""
    created = int(time.time())
    for token in SCRIPTED_TOKENS:
        chunk = {
            "id": f"{STUB_CHUNK_ID_BASE}-{request_id}",
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "delta": {"content": token},
                    "finish_reason": None,
                }
            ],
        }
        yield f"data: {json.dumps(chunk)}\n\n".encode()
        await asyncio.sleep(0.01)

    # Final chunk with finish_reason
    final_chunk = {
        "id": f"{STUB_CHUNK_ID_BASE}-{request_id}",
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(final_chunk)}\n\n".encode()

    # [DONE] sentinel
    yield b"data: [DONE]\n\n"


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint.

    When ``stream=True``, returns an SSE stream of scripted chunks.
    When ``stream=False``, returns a single JSON completion.
    """
    body = await request.json()
    model = body.get("model", STUB_MODEL)
    stream = body.get("stream", False)
    messages = body.get("messages", [])
    request_id = str(uuid.uuid4())[:8]
    is_tool_request = _is_list_networks_request(messages)

    if stream:
        generator = (
            _generate_tool_call_sse_stream(request_id, model)
            if is_tool_request
            else _generate_sse_stream(request_id, model)
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # Non-streaming: return a single completion
    created = int(time.time())

    if is_tool_request:
        tool_call_id = f"{STUB_TOOL_CALL_ID}-{request_id}"
        completion = {
            "id": f"{STUB_CHUNK_ID_BASE}-{request_id}",
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": "list_networks",
                                    "arguments": '{"limit": 10, "offset": 0}',
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        return JSONResponse(content=completion)

    full_content = "".join(SCRIPTED_TOKENS)
    completion = {
        "id": f"{STUB_CHUNK_ID_BASE}-{request_id}",
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": full_content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": len(SCRIPTED_TOKENS),
            "total_tokens": 10 + len(SCRIPTED_TOKENS),
        },
    }
    return JSONResponse(content=completion)
