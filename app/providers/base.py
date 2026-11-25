import os
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.errors import ClearanceError


class ModelError(Exception):
    """The model provider failed while completing a turn."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class Turn(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    token_count: int | None = None


class Model(Protocol):
    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> Turn:
        """Return the next turn. Tool calls and text may both be empty."""


def open_model(kind: str, script: Sequence[Turn] | None = None) -> Model:
    if kind == "fake":
        from app.providers.fake import FakeLLM

        return FakeLLM(list(script or []))
    if kind == "live":
        key = os.environ.get("XAI_API_KEY", "").strip()
        if not key:
            raise ClearanceError(
                "XAI_API_KEY is not set. Use fake, or set the key and choose live.",
            )
        from app.providers.xai import XaiClient

        return XaiClient(key)
    raise ClearanceError("The model choice must be fake or live.")
