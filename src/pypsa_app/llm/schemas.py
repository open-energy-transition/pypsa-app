"""Request and response schemas for the chat/LLM module."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user message to send.")
    history: list[ChatMessage] = Field(
        default_factory=list,
        description=(
            "Prior conversation turns (user/assistant pairs). "
            "Persisted by the client; the backend is stateless."
        ),
    )
    model: str | None = Field(
        default=None,
        description=(
            "Optional model override. Must be available at the configured "
            "LLM provider. Falls back to the server default when omitted."
        ),
    )


class ChatResponse(BaseModel):
    reply: str
    model: str = Field(..., description="Model that actually produced the reply.")
