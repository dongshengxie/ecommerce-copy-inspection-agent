from __future__ import annotations

from agent.issue_fusion import fuse_issues
from contracts.models import Issue, RiskLevel
from llm.models import SemanticSkillResult


def _issue(*, source: str, risk_level: RiskLevel, evidence_span: str) -> Issue:
    return Issue(
        field="description",
        issue_type="医疗功效宣称",
        risk_level=risk_level,
        evidence_span=evidence_span,
        evidence="商品描述",
        rule_ids=["food_claim_001"],
        source=[source],
        confidence=1.0,
        suggestion="删除功效宣称",
    )


def test_fusion_retains_tool_issue_and_requires_review_when_semantic_conclusion_conflicts() -> None:
    tool_issue = _issue(
        source="food_rule_expression_check", risk_level=RiskLevel.HIGH, evidence_span="治疗失眠"
    )
    semantic_issue = _issue(
        source="semantic_risk_skill", risk_level=RiskLevel.MEDIUM, evidence_span="改善睡眠"
    )

    result = fuse_issues(
        [tool_issue],
        SemanticSkillResult(issues=[semantic_issue], review_required=False),
    )

    assert result.issues == [tool_issue]
    assert result.review_required is True
    assert result.review_reasons == ["Tool/Rule/LLM 结论冲突"]
