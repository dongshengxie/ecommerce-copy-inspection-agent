from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.models import Issue, ProductInput, TraceEvent
from contracts.optimization import OptimizationRequest, OptimizationResult


def _valid_product() -> dict[str, object]:
    return {
        "product_id": "food-001",
        "product_revision": 1,
        "category": "食品",
        "title": "茉莉花茶 30g",
        "selling_points": ["独立袋泡"],
        "description": "清香口感。",
        "attributes": {
            "ingredients": "绿茶、茉莉花",
            "shelf_life": "18个月",
            "storage_method": "阴凉干燥处保存",
            "origin": "浙江省杭州市",
        },
        "marketing_description": "30g 盒装。",
        "trigger_source": "test",
    }


def _valid_issue() -> dict[str, object]:
    return {
        "field": "description",
        "issue_type": "医疗功效宣称",
        "risk_level": "high",
        "evidence_span": "治疗失眠",
        "evidence": "命中明确表达。",
        "rule_ids": ["food_claim_001"],
        "source": ["forbidden_expression_checker"],
        "confidence": 1.0,
        "suggestion": "删除治疗暗示。",
    }


def test_food_product_rejects_non_food_category() -> None:
    payload = _valid_product()
    payload["category"] = "美妆"

    with pytest.raises(ValidationError):
        ProductInput.model_validate(payload)


def test_food_product_requires_minimum_attributes() -> None:
    payload = _valid_product()
    attributes = payload["attributes"]
    assert isinstance(attributes, dict)
    attributes.pop("ingredients")

    with pytest.raises(ValidationError):
        ProductInput.model_validate(payload)


def test_issue_requires_evidence_span() -> None:
    payload = _valid_issue()
    payload["evidence_span"] = ""

    with pytest.raises(ValidationError):
        Issue.model_validate(payload)


def test_trace_event_defaults_metadata_to_an_empty_object() -> None:
    trace = TraceEvent(
        task_id="task-001",
        step_name="load_rules",
        tool_or_skill_name="rule_loader",
        decision="加载规则",
        status="success",
        latency_ms=0,
    )

    assert trace.metadata == {}


def test_optimization_request_rejects_unwritable_and_duplicate_fields() -> None:
    with pytest.raises(ValidationError):
        OptimizationRequest.model_validate({"fields": ["attributes"]})
    with pytest.raises(ValidationError, match="优化字段不能重复"):
        OptimizationRequest(fields=["title", "title"])


def test_optimization_result_is_separate_from_inspection_report() -> None:
    result = OptimizationResult(
        optimization_id="opt-001",
        source_task_id="task-001",
        status="failed",
        requested_fields=["title"],
        failure_reason="llm_failed",
    )

    assert result.verification_report is None
    assert result.optimized_fields == {}
