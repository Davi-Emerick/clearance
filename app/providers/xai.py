import json
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from app.errors import ClearanceError
from app.providers.base import ModelError, ToolCall, Turn

# Copied from https://docs.x.ai/developers/models/grok-4.7 on 2026-11-25.
MODEL_ID = "grok-4.7"
BASE_URL = "https://api.x.ai/v1"
TIMEOUT_SECONDS = 60.0


class XaiClient:
    def __init__(self, api_key: str):
        key = api_key.strip()
        if not key:
            raise ClearanceError(
                "XAI_API_KEY is not set. Use fake, or set the key and choose live.",
            )
        self._api_key = key

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> Turn:
        response = httpx.post(
            f"{BASE_URL}/responses",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": MODEL_ID,
                "input": _input_items(messages),
                "tools": [_tool(item) for item in tools],
                "temperature": 0,
                "store": False,
            },
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise ModelError(f"The model request failed with status {response.status_code}.")
        body = response.json()
        if not isinstance(body, dict):
            raise ModelError("The model response was not a JSON object.")
        return _turn(body)


def _input_items(messages: Sequence[Mapping[str, Any]]) -> list[dict]:
    items: list[dict] = []
    for message in messages:
        role = str(message.get("role", "user"))
        if role == "tool":
            items.append({
                "type": "function_call_output",
                "call_id": str(message.get("tool_call_id", "")),
                "output": str(message.get("content", "")),
            })
            continue
        content = message.get("content", "")
        if content:
            items.append({"role": role, "content": str(content)})
        for call in message.get("tool_calls") or []:
            arguments = call.get("arguments", {})
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments)
            items.append({
                "type": "function_call",
                "call_id": str(call.get("id", "")),
                "name": str(call.get("name", "")),
                "arguments": arguments,
            })
    return items


def _tool(item: Mapping[str, Any]) -> dict:
    tool = {
        "type": "function",
        "name": str(item["name"]),
        "parameters": item.get("parameters") or {"type": "object", "properties": {}},
    }
    description = item.get("description")
    if description:
        tool["description"] = str(description)
    return tool


def _turn(body: Mapping[str, Any]) -> Turn:
    texts: list[str] = []
    calls: list[ToolCall] = []
    for item in body.get("output") or []:
        if not isinstance(item, Mapping):
            continue
        kind = item.get("type")
        if kind == "function_call":
            calls.append(_tool_call(item))
        elif kind == "message":
            texts.extend(_message_text(item.get("content")))
    usage = body.get("usage")
    token_count = None
    if isinstance(usage, Mapping) and "total_tokens" in usage:
        token_count = int(usage["total_tokens"])
    return Turn(text="".join(texts), tool_calls=calls, token_count=token_count)


def _message_text(content: Any) -> list[str]:
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []
    texts = []
    for part in content:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, Mapping) and part.get("type") in {None, "output_text", "text"}:
            texts.append(str(part.get("text", "")))
    return texts


def _tool_call(item: Mapping[str, Any]) -> ToolCall:
    raw = item.get("arguments", "{}")
    if isinstance(raw, str):
        try:
            arguments = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError as exc:
            raise ModelError("The model returned a tool call that is not JSON.") from exc
    elif isinstance(raw, Mapping):
        arguments = dict(raw)
    else:
        raise ModelError("The model returned a tool call that is not JSON.")
    if not isinstance(arguments, dict):
        raise ModelError("The model returned a tool call that is not JSON.")
    return ToolCall(
        id=str(item.get("call_id") or item.get("id") or ""),
        name=str(item.get("name") or ""),
        arguments=arguments,
    )
