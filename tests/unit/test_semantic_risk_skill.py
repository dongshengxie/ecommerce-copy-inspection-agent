from __future__ import annotations

from contracts.models import FoodAttributes, ProductInput, RiskLevel, Rule
from llm.models import LLMResponse
from llm.semantic_risk import SemanticRiskSkill
from rag.models import RetrievalCandidate


def _product() -> ProductInput:
    return ProductInput(
        product_id="product-1",
        product_revision=1,
        category="食品",
        title="茉莉花茶",
        selling_points=[],
        description="这款茶可以改善睡眠。",
        attributes=FoodAttributes(
            ingredients="茶叶",
            shelf_life="18个月",
            storage_method="阴凉干燥处保存",
            origin="福建",
        ),
        marketing_description="",
        trigger_source="manual",
    )


def _candidate() -> RetrievalCandidate:
    rule = Rule(
        rule_id="food_health_002",
        version="1.0.0",
        category="食品",
        field_scope=["description"],
        issue_type="保健功能暗示",
        risk_level=RiskLevel.MEDIUM,
        rule_strength="normal",
        rule_text="不得作出未经依据支撑的保健功能暗示",
        bad_examples=["改善睡眠"],
        rewrite_hint="描述产品风味",
        status="enabled",
        effective_at="2026-01-01",
    )
    return RetrievalCandidate(rule=rule, rrf_score=0.03, reranker_score=0.9)


class _FakeLLM:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.call_count = 0

    def complete_structured(self, messages: list[dict[str, str]]) -> LLMResponse:
        assert messages[0]["role"] == "system"
        response = self.responses[self.call_count]
        self.call_count += 1
        return LLMResponse(
            payload=response,
            model_name="deepseek-chat",
            input_tokens=10,
            output_tokens=5,
            latency_ms=20,
        )


def test_semantic_skill_creates_issue_only_for_candidate_rule_and_exact_evidence() -> None:
    skill = SemanticRiskSkill(
        llm_provider=_FakeLLM(
            [
                {
                    "findings": [
                        {
                            "rule_id": "food_health_002",
                            "rule_version": "1.0.0",
                            "field": "description",
                            "evidence_span": "改善睡眠",
                            "rationale": "出现身体功能改善暗示",
                            "suggestion": "改为描述口感",
                            "confidence": 0.75,
                        }
                    ]
                }
            ]
        ),
        prompt_version="1.0.0",
    )

    result = skill.inspect(_product(), [_candidate()], [])

    assert result.issues[0].rule_ids == ["food_health_002"]
    assert result.issues[0].evidence_span == "改善睡眠"
    assert result.issues[0].risk_level is RiskLevel.MEDIUM
    assert result.review_required is False
    assert result.trace_metadata == {
        "prompt_version": "1.0.0",
        "model_name": "deepseek-chat",
        "input_tokens": 10,
        "output_tokens": 5,
        "latency_ms": 20,
    }


def test_semantic_skill_retries_once_then_requires_review_for_invalid_output() -> None:
    llm = _FakeLLM([{"unexpected": []}, {"still_unexpected": []}])
    skill = SemanticRiskSkill(llm_provider=llm, prompt_version="1.0.0")

    result = skill.inspect(_product(), [_candidate()], [])

    assert result.issues == []
    assert result.degradation_flags == ["structured_output_invalid"]
    assert result.review_required is True
    assert llm.call_count == 2


def test_semantic_skill_rejects_evidence_that_is_not_in_the_reported_source_field() -> None:
    invalid_finding = {
        "findings": [
            {
                "rule_id": "food_health_002",
                "rule_version": "1.0.0",
                "field": "description",
                "evidence_span": "不存在的文本",
                "rationale": "错误定位",
                "suggestion": "改为描述口感",
                "confidence": 0.75,
            }
        ]
    }
    skill = SemanticRiskSkill(
        llm_provider=_FakeLLM([invalid_finding, invalid_finding]),
        prompt_version="1.0.0",
    )

    result = skill.inspect(_product(), [_candidate()], [])

    assert result.issues == []
    assert result.degradation_flags == ["structured_output_invalid"]
