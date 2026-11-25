from collections.abc import Mapping, Sequence
from typing import Any

from app.providers.base import Turn


class FakeLLM:
    model_id = "fake"

    def __init__(self, turns: Sequence[Turn]):
        self._turns = list(turns)
        self._index = 0

    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> Turn:
        if self._index >= len(self._turns):
            return Turn()
        turn = self._turns[self._index]
        self._index += 1
        return turn
