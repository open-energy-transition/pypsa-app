"""Chat endpoint for the LLM integration.

Uses the Anthropic SDK against any Anthropic-compatible provider (Ollama,
llama.cpp, OpenRouter, or api.anthropic.com). The provider is selected by
`ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY`; the model by `LLM_MODEL_DEFAULT`
or a per-request override.
"""

import asyncio
import json
import logging
from typing import Any

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from pypsa_app.backend.api.deps import get_active_user, get_db
from pypsa_app.backend.models import User
from pypsa_app.backend.settings import settings
from pypsa_app.llm.schemas import ChatRequest, ChatResponse
from pypsa_app.llm.tools import REGISTRY, anthropic_tool_specs

logger = logging.getLogger(__name__)

router = APIRouter()


def _build_client() -> anthropic.AsyncAnthropic:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Chat is not configured. Set ANTHROPIC_API_KEY (use the "
                "literal value 'ollama' when pointing at a local Ollama)."
            ),
        )
    return anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        base_url=settings.anthropic_base_url,
    )


async def _create_message(
    client: anthropic.AsyncAnthropic,
    **kwargs: Any,
) -> anthropic.types.Message:
    """Call `messages.create` and map provider errors to HTTP responses."""
    try:
        return await client.messages.create(**kwargs)
    except anthropic.AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM provider authentication failed: {exc.message}",
        ) from exc
    except anthropic.RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="LLM provider rate limit exceeded.",
        ) from exc
    except anthropic.BadRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        ) from exc
    except anthropic.APIConnectionError as exc:
        logger.exception(
            "Could not reach LLM provider at %s", settings.anthropic_base_url
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM provider unreachable.",
        ) from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM provider error: {exc.message}",
        ) from exc


async def _execute_tool(
    name: str,
    tool_input: dict[str, Any],
    *,
    db: Session,
    user: User,
) -> tuple[str, bool]:
    """Run a registered tool. Returns ``(content, is_error)``."""
    tool = REGISTRY.get(name)
    if tool is None:
        logger.warning("LLM called unknown tool %s", name)
        return f"Unknown tool: {name}", True
    logger.info("LLM tool call: %s input=%s", name, tool_input)
    try:
        result = await asyncio.to_thread(
            tool.handler, db=db, user=user, **tool_input
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Tool %s failed", name)
        return f"Tool {name} failed: {type(exc).__name__}", True
    return json.dumps(result, default=str), False


@router.post("/", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    user: User = Depends(get_active_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    client = _build_client()
    model = req.model or settings.llm_model_default
    messages: list[dict[str, Any]] = [
        *(m.model_dump() for m in req.history),
        {"role": "user", "content": req.message},
    ]
    thinking = (
        {"type": "enabled", "budget_tokens": settings.llm_thinking_budget_tokens}
        if settings.llm_thinking_enabled
        else {"type": "disabled"}
    )
    tool_specs = anthropic_tool_specs()

    response: anthropic.types.Message | None = None
    truncated = False
    for _ in range(settings.llm_max_tool_iterations):
        response = await _create_message(
            client,
            model=model,
            max_tokens=settings.llm_max_tokens,
            system=settings.llm_system_prompt,
            messages=messages,
            tools=tool_specs,
            thinking=thinking,
        )

        if response.stop_reason != "tool_use":
            break

        messages.append(
            {
                "role": "assistant",
                "content": [block.model_dump() for block in response.content],
            }
        )
        tool_results: list[dict[str, Any]] = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            content_str, is_error = await _execute_tool(
                block.name, block.input, db=db, user=user
            )
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content_str,
                    "is_error": is_error,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    if response is not None and response.stop_reason == "tool_use":
        # Cap hit mid-flight: nudge the model to summarize and stop using tools.
        truncated = True
        logger.warning(
            "Tool-use loop hit cap of %s iterations; soft-stopping",
            settings.llm_max_tool_iterations,
        )
        messages[-1]["content"].append(
            {
                "type": "text",
                "text": (
                    "[System notice] You have reached the maximum of "
                    f"{settings.llm_max_tool_iterations} tool calls for this "
                    "turn. Stop calling tools now. Summarize for the user what "
                    "you have found so far, describe what remains unexamined, "
                    "and tell them they can reply 'continue' if they want you "
                    "to keep exploring."
                ),
            }
        )
        response = await _create_message(
            client,
            model=model,
            max_tokens=settings.llm_max_tokens,
            system=settings.llm_system_prompt,
            messages=messages,
            thinking=thinking,
        )

    reply = next((b.text for b in response.content if b.type == "text"), "")
    return ChatResponse(reply=reply, model=response.model, truncated=truncated)
