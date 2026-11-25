import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.providers.base import ToolCall, Turn
from app.services.clearance import FACT_NAMES


class DemoScript:
    """Fixed desk script for CLEARANCE_MODEL=fake. It does not call a model."""

    model_id = "fake"

    def __init__(self):
        self._stage = 0

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> Turn:
        payloads = _tool_payloads(messages)
        if self._stage == 0:
            self._stage = 1
            return _call("demo-list", "list_documents", {})
        if self._stage == 1:
            self._stage = 2
            documents = payloads[-1].get("documents", []) if payloads else []
            return Turn(tool_calls=[
                ToolCall(id=f"demo-read-{index}", name="read_document", arguments={"document_id": item["id"]})
                for index, item in enumerate(documents)
            ])
        if self._stage == 2:
            self._stage = 3
            return _call("demo-facts", "record_facts", {"facts": _cited_facts(payloads)})
        if self._stage == 3:
            self._stage = 4
            return _call("demo-eval", "evaluate", {})
        if self._stage == 4:
            self._stage = 5
            legal = payloads[-1] if payloads else {}
            return _call("demo-submit", "submit_memo", {
                "recommendation": legal.get("recommendation", ""),
                "premium": 1,
                "carrier": "Paper Street Indemnity",
            })
        return Turn()


def _call(call_id: str, name: str, arguments: dict) -> Turn:
    return Turn(tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)])


def _tool_payloads(messages: Sequence[Mapping[str, Any]]) -> list[dict]:
    found = []
    for message in messages:
        if message.get("role") != "tool":
            continue
        content = message.get("content") or ""
        if isinstance(content, dict):
            found.append(content)
            continue
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            found.append(payload)
    return found


def _cited_facts(payloads: list[dict]) -> list[dict]:
    facts = []
    for payload in payloads:
        body = payload.get("body_text")
        document_id = payload.get("id")
        if not body or not document_id:
            continue
        for line in str(body).splitlines():
            if ":" not in line:
                continue
            name, value = line.split(":", 1)
            name = name.strip()
            value = value.strip()
            if name not in FACT_NAMES or not value:
                continue
            facts.append({
                "name": name,
                "value": value,
                "document_id": document_id,
                "quote": line.strip(),
            })
    return facts
