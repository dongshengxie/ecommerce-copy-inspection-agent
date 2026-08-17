from contracts.models import Issue, RiskLevel
from tools.food.risk import aggregate_risk


def _issue(risk_level: RiskLevel) -> Issue:
    return Issue(
        field="title",
        issue_type="test",
        risk_level=risk_level,
        evidence_span="test",
        evidence="test",
        rule_ids=["rule"],
        source=["test"],
        confidence=1.0,
        suggestion="test",
    )


def test_aggregate_risk_returns_pass_without_issues() -> None:
    assert aggregate_risk([]) is RiskLevel.PASS


def test_aggregate_risk_returns_high_when_low_and_high_issues_exist() -> None:
    assert aggregate_risk([_issue(RiskLevel.LOW), _issue(RiskLevel.HIGH)]) is RiskLevel.HIGH
