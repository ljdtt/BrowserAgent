"""Small compatibility layer around Qwen-Agent chat models."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from qwen_agent.llm import get_chat_model


class ModelResponseError(RuntimeError):
    """Raised when a model response cannot be used by the agent loop."""


class QwenModelAdapter:
    """Normalize Qwen-Agent responses to one assistant message dictionary."""

    def __init__(self, model=None, config: dict[str, Any] | None = None):
        self._model = model
        self._config = config or {}

    @property
    def model(self):
        if self._model is None:
            self._model = get_chat_model(self._config)
        return self._model

    def next(self, messages: list[dict[str, Any]], functions: list[dict[str, Any]]) -> dict[str, Any]:
        responses = self.model.chat(messages=messages, functions=functions, stream=False)
        normalized = self._as_list(responses)
        if not normalized:
            raise ModelResponseError("empty model response")

        message = normalized[-1]
        if hasattr(message, "model_dump"):
            message = message.model_dump(exclude_none=True)
        elif not isinstance(message, dict):
            try:
                message = dict(message)
            except (TypeError, ValueError) as exc:
                raise ModelResponseError("invalid model response") from exc

        if not isinstance(message, dict):
            raise ModelResponseError("invalid model response")
        return message

    @staticmethod
    def _as_list(responses: Any) -> list[Any]:
        if responses is None:
            return []
        if isinstance(responses, list):
            return responses
        if isinstance(responses, (dict, str, bytes)):
            return [responses]
        if isinstance(responses, Iterable):
            batches = list(responses)
            if not batches:
                return []
            last_batch = batches[-1]
            return last_batch if isinstance(last_batch, list) else batches
        return [responses]
