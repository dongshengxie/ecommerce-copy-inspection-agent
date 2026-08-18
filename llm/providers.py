from __future__ import annotations

import json
from time import perf_counter
from typing import Protocol

import httpx

from llm.models import LLMResponse


class LLMUnavailableError(RuntimeError):
    """An LLM provider failed in a way the workflow can safely degrade from."""


class LLMProvider(Protocol):
    """The minimal structured-completion boundary used by semantic inspection."""

    def complete_structured(self, messages: list[dict[str, str]]) -> LLMResponse:
        """Return JSON output plus safe model usage metadata."""


class DeepSeekProvider:
    """Call DeepSeek's documented JSON-output chat completion endpoint."""

    def __init__(
        self,
        *,
        client: httpx.Client,
        api_key: str,
        model: str,
        base_url: str = "https://api.deepseek.com",
    ) -> None:
        self._client = client
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    def complete_structured(self, messages: list[dict[str, str]]) -> LLMResponse:
        started_at = perf_counter()
        try:
            response = self._client.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "stream": False,
                },
                timeout=20.0,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            structured_payload = json.loads(content)
            usage = payload.get("usage", {})
            if not isinstance(structured_payload, dict) or not isinstance(usage, dict):
                raise ValueError("DeepSeek response does not contain a JSON object")
            return LLMResponse(
                payload=structured_payload,
                model_name=str(payload.get("model", self._model)),
                input_tokens=int(usage.get("prompt_tokens", 0)),
                output_tokens=int(usage.get("completion_tokens", 0)),
                latency_ms=int((perf_counter() - started_at) * 1000),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise LLMUnavailableError("deepseek_completion_failed") from error
