"""Shared test fixtures and fakes for the LLM test suite."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel


@dataclass
class FakeNetwork:
    """Duck-types pypsa_app.backend.models.Network for serializer tests."""

    id: UUID
    user_id: UUID
    name: str | None
    filename: str
    visibility: Any
    created_at: datetime | None = None


@dataclass
class FakeVisibility:
    value: str


@dataclass
class FakeUser:
    id: UUID = field(default_factory=uuid4)


class FakeTextBlock(BaseModel):
    type: Literal["text"] = "text"
    text: str


class FakeToolUseBlock(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


class FakeMessage(BaseModel):
    content: list[FakeTextBlock | FakeToolUseBlock]
    stop_reason: str
    model: str = "fake-model"


class FakeAnthropicClient:
    """Returns queued ``FakeMessage`` responses in order and records calls."""

    def __init__(self, responses: list[FakeMessage]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    @property
    def messages(self) -> FakeAnthropicClient:
        return self

    async def create(self, **kwargs: Any) -> FakeMessage:
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeAnthropicClient exhausted")
        return self._responses.pop(0)


@pytest.fixture
def fake_user() -> FakeUser:
    return FakeUser()


def make_network(
    *,
    owner_id: UUID,
    name: str | None = "net-a",
    filename: str = "net-a.nc",
    visibility: str = "private",
    created_at: datetime | None = None,
) -> FakeNetwork:
    return FakeNetwork(
        id=uuid4(),
        user_id=owner_id,
        name=name,
        filename=filename,
        visibility=FakeVisibility(value=visibility),
        created_at=created_at or datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
    )
