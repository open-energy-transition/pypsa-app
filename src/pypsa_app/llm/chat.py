"""Chat endpoint for the LLM integration.

Uses the Anthropic SDK against any Anthropic-compatible provider (Ollama,
llama.cpp, OpenRouter, or api.anthropic.com). The provider is selected by
`ANTHROPIC_BASE_URL` + `ANTHROPIC_API_KEY`; the model by `LLM_MODEL_DEFAULT`
or a per-request override.
"""

import logging

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status

from pypsa_app.backend.api.deps import get_active_user
from pypsa_app.backend.models import User
from pypsa_app.backend.settings import settings
from pypsa_app.llm.schemas import ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter()

SYSTEM_PROMPT = (
    "You are a helpful assistant for PyPSA, an open-source energy system "
    "optimization framework. Keep replies concise and accurate. If you are "
    "unsure about something, say so rather than guessing."
)

MAX_TOKENS = 16000


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


@router.post("/", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    _user: User = Depends(get_active_user),
) -> ChatResponse:
    client = _build_client()
    model = req.model or settings.llm_model_default
    messages = [
        *(m.model_dump() for m in req.history),
        {"role": "user", "content": req.message},
    ]
    thinking = (
        {"type": "enabled", "budget_tokens": 4000}
        if settings.llm_thinking_enabled
        else {"type": "disabled"}
    )

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=messages,
            thinking=thinking,
        )
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

    reply = next((b.text for b in response.content if b.type == "text"), "")
    return ChatResponse(reply=reply, model=response.model)
