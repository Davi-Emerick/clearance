import pytest

from app.errors import ClearanceError
from app.providers.base import ToolCall, Turn, open_model
from app.providers.fake import FakeLLM


def test_fake_returns_the_script_then_an_empty_turn():
    model = FakeLLM([
        Turn(text="Read the folder.", token_count=4),
        Turn(tool_calls=[ToolCall(id="call-1", name="list_documents", arguments={})]),
    ])
    first = model.complete([], [])
    assert first.text == "Read the folder."
    assert first.token_count == 4
    assert first.tool_calls == []

    second = model.complete(
        [{"role": "user", "content": "case-1"}],
        [{"name": "list_documents", "parameters": {"type": "object", "properties": {}}}],
    )
    assert second.text == ""
    assert second.tool_calls[0].name == "list_documents"
    assert second.tool_calls[0].id == "call-1"

    empty = model.complete([], [])
    again = model.complete([], [])
    assert empty == Turn()
    assert again == Turn()


def test_without_a_key_fake_is_allowed_and_live_is_refused(monkeypatch):
    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("The live client called the network.")

    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setattr("httpx.post", fail_if_called)

    model = open_model("fake", script=[Turn(text="ok", token_count=1)])
    assert isinstance(model, FakeLLM)
    assert model.complete([], []).text == "ok"

    with pytest.raises(ClearanceError, match="XAI_API_KEY"):
        open_model("live")
