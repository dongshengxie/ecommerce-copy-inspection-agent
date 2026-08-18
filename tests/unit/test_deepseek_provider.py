from __future__ import annotations

import json

import httpx

from llm.providers import DeepSeekProvider


def test_deepseek_provider_returns_parsed_json_and_safe_usage_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert json.loads(request.content) == {
            "model": "deepseek-chat",
            "messages": [{"role": "system", "content": "请返回 json"}],
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        return httpx.Response(
            200,
            json={
                "model": "deepseek-chat",
                "choices": [{"message": {"content": '{"findings": []}'}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 4},
            },
        )

    response = DeepSeekProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        api_key="test-key",
        model="deepseek-chat",
    ).complete_structured([{"role": "system", "content": "请返回 json"}])

    assert response.payload == {"findings": []}
    assert response.model_name == "deepseek-chat"
    assert response.input_tokens == 12
    assert response.output_tokens == 4
