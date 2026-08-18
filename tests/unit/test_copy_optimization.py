from __future__ import annotations

from contracts.models import (
    FoodAttributes,
    InspectionReport,
    Issue,
    ProductInput,
    RiskLevel,
    Rule,
    TaskStatus,
)
from contracts.optimization import OptimizationRequest
from llm.copy_optimization import CopyOptimizationSkill
from llm.models import LLMResponse


def _product() -> ProductInput:
    return ProductInput(
        product_id="product-1",
        product_revision=1,
        category="食品",
        title="谷物冲饮粉 300g",
        selling_points=["谷物风味"],
        description="300g 香浓谷物口感，有助于改善睡眠。",
        attributes=FoodAttributes(
            ingredients="燕麦、黑芝麻、麦芽糊精",
            shelf_life="12个月",
            storage_method="密封干燥保存",
            origin="江苏省苏州市",
        ),
        marketing_description="每日一杯。",
        trigger_source="test",
    )


def _rule() -> Rule:
    return Rule(
        rule_id="food_health_002",
        version="1.0.0",
        category="食品",
        field_scope=["description"],
        issue_type="保健功能暗示",
        risk_level=RiskLevel.MEDIUM,
        rule_strength="normal",
        rule_text="普通食品文案应避免未经依据支撑的保健或身体功能改善暗示。",
        bad_examples=["改善睡眠"],
        rewrite_hint="删除功能改善暗示，改为描述原料、口感或冲泡方式。",
        status="enabled",
        effective_at="2026-01-01",
    )


def _report() -> InspectionReport:
    return InspectionReport(
        task_id="task-1",
        status=TaskStatus.SUCCESS,
        automated_risk_level=RiskLevel.MEDIUM,
        review_required=False,
        issues=[
            Issue(
                field="description",
                issue_type="保健功能暗示",
                risk_level=RiskLevel.MEDIUM,
                evidence_span="改善睡眠",
                evidence="出现身体功能改善暗示。",
                rule_ids=["food_health_002"],
                source=["semantic_risk_skill"],
                confidence=0.75,
                suggestion="改为描述谷物口感。",
            )
        ],
        trace_id="task-1",
    )


class _FakeLLM:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self._payloads = payloads
        self._index = 0

    def complete_structured(self, messages: list[dict[str, str]]) -> LLMResponse:
        assert messages[0]["role"] == "system"
        payload = self._payloads[self._index]
        self._index += 1
        return LLMResponse(
            payload=payload,
            model_name="deepseek-chat",
            input_tokens=12,
            output_tokens=8,
            latency_ms=20,
        )


def test_copy_optimization_returns_only_requested_fields_and_safe_metadata() -> None:
    skill = CopyOptimizationSkill(
        llm_provider=_FakeLLM(
            [{"optimized_fields": {"description": "300g 香浓谷物口感，适合日常冲泡饮用。"}}]
        ),
        prompt_version="1.0.0",
    )

    artifact = skill.optimize(
        _product(),
        _report(),
        [_rule()],
        OptimizationRequest(fields=["description"]),
    )

    assert artifact.optimized_fields == {"description": "300g 香浓谷物口感，适合日常冲泡饮用。"}
    assert artifact.referenced_rule_ids == ["food_health_002"]
    assert artifact.failure_reason is None
    assert artifact.safe_metadata == {
        "provider": "deepseek",
        "prompt_name": "copy_optimization",
        "prompt_version": "1.0.0",
        "model_name": "deepseek-chat",
        "input_tokens": 12,
        "output_tokens": 8,
        "latency_ms": 20,
        "retry_count": 0,
        "schema_valid": True,
        "repair_attempted": False,
        "operation": "copy_optimization",
    }
    assert "prompt" not in artifact.safe_metadata
    assert "raw_output" not in artifact.safe_metadata


def test_copy_optimization_rejects_unrequested_fields_and_missing_protected_specification() -> None:
    skill = CopyOptimizationSkill(
        llm_provider=_FakeLLM(
            [
                {"optimized_fields": {"title": "谷物冲饮粉 300g"}},
                {"optimized_fields": {"description": "香浓谷物口感，适合冲泡饮用。"}},
            ]
        ),
        prompt_version="1.0.0",
    )

    artifact = skill.optimize(
        _product(),
        _report(),
        [_rule()],
        OptimizationRequest(fields=["description"]),
    )

    assert artifact.optimized_fields == {}
    assert artifact.failure_reason == "optimization_output_invalid"
    assert artifact.safe_metadata["retry_count"] == 1
    assert artifact.safe_metadata["schema_valid"] is False
    assert artifact.safe_metadata["repair_attempted"] is True


def test_copy_optimization_rejects_explicit_conflict_with_protected_attributes() -> None:
    conflicting_payload = {"optimized_fields": {"description": "300g 配料为人参，香浓谷物口感。"}}
    skill = CopyOptimizationSkill(
        llm_provider=_FakeLLM([conflicting_payload, conflicting_payload]),
        prompt_version="1.0.0",
    )

    artifact = skill.optimize(
        _product(),
        _report(),
        [_rule()],
        OptimizationRequest(fields=["description"]),
    )

    assert artifact.failure_reason == "optimization_output_invalid"
    assert artifact.optimized_fields == {}
