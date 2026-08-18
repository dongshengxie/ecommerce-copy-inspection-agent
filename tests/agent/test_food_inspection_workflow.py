from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.graph.food_inspection_workflow import FoodInspectionWorkflow
from contracts.models import ProductInput, RiskLevel, Rule
from llm.models import SemanticSkillResult
from skills.food.quality import FoodQualitySkill

ROOT = Path(__file__).resolve().parents[2]


def _load_rules() -> list[Rule]:
    with (ROOT / "data/rules/food_rules.json").open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


def _case_input(case_id: str) -> ProductInput:
    with (ROOT / "evaluation/datasets/food_golden_dataset.json").open(encoding="utf-8") as file:
        cases = json.load(file)
    case = next(item for item in cases if item["case_id"] == case_id)
    return ProductInput.model_validate(case["input"])


def test_workflow_returns_pass_and_fixed_node_traces_for_case_001() -> None:
    result = FoodInspectionWorkflow(_load_rules, FoodQualitySkill()).invoke(
        task_id="task-001", product=_case_input("food_case_001")
    )

    assert result.report.automated_risk_level is RiskLevel.PASS
    assert [trace.step_name for trace in result.trace_events] == [
        "load_rules",
        "food_quality_skill",
        "semantic_risk_skill",
        "issue_fusion",
        "risk_aggregator",
        "report_builder",
    ]


def test_workflow_returns_high_and_review_required_for_case_004() -> None:
    result = FoodInspectionWorkflow(_load_rules, FoodQualitySkill()).invoke(
        task_id="task-004", product=_case_input("food_case_004")
    )

    assert len(result.report.issues) == 6
    assert result.report.automated_risk_level is RiskLevel.HIGH
    assert result.report.review_required is True


def test_workflow_propagates_rule_loader_failure() -> None:
    def failing_loader() -> list[Rule]:
        raise RuntimeError("rule store unavailable")

    with pytest.raises(RuntimeError, match="rule store unavailable"):
        FoodInspectionWorkflow(failing_loader, FoodQualitySkill()).invoke(
            task_id="task-failure", product=_case_input("food_case_001")
        )


class _FakeSemanticInspectionSkill:
    def __init__(self, result: SemanticSkillResult) -> None:
        self._result = result

    def inspect(
        self, product: ProductInput, rules: list[Rule], deterministic_issues: list[object]
    ) -> SemanticSkillResult:
        assert product.category == "食品"
        assert rules
        assert isinstance(deterministic_issues, list)
        return self._result


def test_workflow_keeps_tool_issues_when_semantic_skill_adds_none() -> None:
    workflow = FoodInspectionWorkflow(
        _load_rules,
        FoodQualitySkill(),
        semantic_inspection_skill=_FakeSemanticInspectionSkill(SemanticSkillResult()),
    )

    result = workflow.invoke(task_id="task-004", product=_case_input("food_case_004"))

    assert len(result.report.issues) == 6
    assert result.report.degradation_flags == []
    assert [trace.step_name for trace in result.trace_events] == [
        "load_rules",
        "food_quality_skill",
        "semantic_risk_skill",
        "issue_fusion",
        "risk_aggregator",
        "report_builder",
    ]


def test_workflow_returns_deterministic_report_when_rag_is_unavailable() -> None:
    workflow = FoodInspectionWorkflow(
        _load_rules,
        FoodQualitySkill(),
        semantic_inspection_skill=_FakeSemanticInspectionSkill(
            SemanticSkillResult(
                degradation_flags=["rag_unavailable"],
                review_required=True,
                trace_metadata={"error_category": "rag_unavailable"},
            )
        ),
    )

    result = workflow.invoke(task_id="task-001", product=_case_input("food_case_001"))

    assert result.report.automated_risk_level is RiskLevel.PASS
    assert result.report.review_required is True
    assert result.report.degradation_flags == ["rag_unavailable"]
