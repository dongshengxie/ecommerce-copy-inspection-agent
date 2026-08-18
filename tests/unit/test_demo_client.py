from __future__ import annotations

import httpx

from app.demo import DemoApiClient
from contracts.models import ProductInput


def _product() -> ProductInput:
    return ProductInput.model_validate(
        {
            "product_id": "demo-product-1",
            "product_revision": 1,
            "category": "食品",
            "title": "谷物冲饮 30g",
            "selling_points": ["独立包装"],
            "description": "清香口感。",
            "attributes": {
                "ingredients": "燕麦",
                "shelf_life": "12个月",
                "storage_method": "阴凉干燥处保存",
                "origin": "浙江",
            },
            "marketing_description": "30g 盒装。",
            "trigger_source": "streamlit_demo",
        }
    )


class _FakeHttpClient:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []

    def post(self, url: str, **kwargs: object) -> httpx.Response:
        return self._response("POST", url, **kwargs)

    def get(self, url: str, **kwargs: object) -> httpx.Response:
        return self._response("GET", url, **kwargs)

    def _response(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        headers = kwargs.get("headers")
        request = httpx.Request(method, url, headers=headers if isinstance(headers, dict) else None)
        self.requests.append(request)
        return httpx.Response(200, request=request, json={"task_id": "task-1"})


def test_demo_client_sets_semantic_header_only_from_checkbox() -> None:
    fake_http = _FakeHttpClient()
    client = DemoApiClient(http_client=fake_http, base_url="http://api")

    client.create_inspection(_product(), semantic_enabled=False)

    assert fake_http.requests[0].headers["X-Semantic-Inspection"] == "disabled"


def test_demo_client_uses_api_for_evidence_trace_and_explicit_optimization() -> None:
    fake_http = _FakeHttpClient()
    client = DemoApiClient(http_client=fake_http, base_url="http://api")

    client.fetch_result("task-1")
    client.fetch_trace("task-1")
    client.fetch_rule_evidence("task-1")
    client.optimize("task-1", ["description"])

    assert [request.url.path for request in fake_http.requests] == [
        "/api/v2/inspections/task-1/result",
        "/api/v2/inspections/task-1/trace",
        "/api/v2/inspections/task-1/rule-evidence",
        "/api/v2/inspections/task-1/optimization",
    ]
