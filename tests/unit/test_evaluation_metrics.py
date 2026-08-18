from __future__ import annotations

import pytest

from contracts.models import RiskLevel, TaskStatus
from evaluation.metrics import build_output_diff, compute_metrics
from evaluation.models import EvaluationCaseResult, NormalizedIssue


def _issue(
    evidence_span: str,
    rule_id: str,
    risk_level: RiskLevel = RiskLevel.MEDIUM,
    confidence: float | None = None,
) -> NormalizedIssue:
    return NormalizedIssue(
        field="description",
        rule_ids=[rule_id],
        evidence_span=evidence_span,
        risk_level=risk_level,
        confidence=confidence,
    )


def _case_result(
    *,
    expected_issues: list[NormalizedIssue],
    observed_issues: list[NormalizedIssue],
    expected_risk_level: RiskLevel = RiskLevel.MEDIUM,
    observed_risk_level: RiskLevel = RiskLevel.MEDIUM,
    review_required: bool = False,
    semantic_metadata: list[dict[str, object]] | None = None,
    evidence_grounded: list[bool] | None = None,
) -> EvaluationCaseResult:
    return EvaluationCaseResult(
        case_id="case-1",
        task_status=TaskStatus.SUCCESS,
        expected_risk_level=expected_risk_level,
        observed_risk_level=observed_risk_level,
        expected_issues=expected_issues,
        observed_issues=observed_issues,
        expected_rule_ids=sorted(
            {rule_id for issue in expected_issues for rule_id in issue.rule_ids}
        ),
        observed_rule_ids=sorted(
            {rule_id for issue in observed_issues for rule_id in issue.rule_ids}
        ),
        review_required=review_required,
        degradation_flags=[],
        latency_ms=100,
        semantic_metadata=semantic_metadata or [],
        observed_evidence_grounded=evidence_grounded or [],
    )


def test_metrics_calculate_precision_recall_high_recall_and_false_positive_rate() -> None:
    expected_high = _issue("治疗失眠", "rule-a", RiskLevel.HIGH)
    expected_medium = _issue("改善睡眠", "rule-b")
    observed_extra = _issue("安全", "rule-c")

    metrics = compute_metrics(
        [
            _case_result(
                expected_issues=[expected_high, expected_medium],
                observed_issues=[expected_high, observed_extra],
                evidence_grounded=[True, True],
            )
        ]
    )

    assert metrics["issue_precision"] == pytest.approx(0.5)
    assert metrics["issue_recall"] == pytest.approx(0.5)
    assert metrics["issue_f1"] == pytest.approx(0.5)
    assert metrics["high_risk_recall"] == pytest.approx(1.0)
    assert metrics["false_positive_rate"] == pytest.approx(0.5)
    assert metrics["rule_citation_precision"] == pytest.approx(0.5)
    assert metrics["rule_citation_recall"] == pytest.approx(0.5)


def test_empty_metric_denominators_are_null_not_zero() -> None:
    metrics = compute_metrics([_case_result(expected_issues=[], observed_issues=[])])

    assert metrics["issue_precision"] is None
    assert metrics["issue_recall"] is None
    assert metrics["high_risk_recall"] is None
    assert metrics["false_positive_rate"] is None
    assert metrics["evidence_grounded_rate"] is None


def test_rewrite_metrics_are_null_without_owner_rewrite_labels() -> None:
    metrics = compute_metrics([_case_result(expected_issues=[], observed_issues=[])])

    assert metrics["rewrite_pass_rate"] is None
    assert metrics["protected_fact_preservation_rate"] is None
    assert metrics["new_risk_introduction_rate"] is None


def test_metrics_read_safe_semantic_metadata_for_schema_and_retrieval() -> None:
    expected = _issue("改善睡眠", "rule-a")
    metrics = compute_metrics(
        [
            _case_result(
                expected_issues=[expected],
                observed_issues=[expected],
                semantic_metadata=[
                    {
                        "schema_valid": True,
                        "repair_attempted": False,
                        "candidate_rule_ids": ["rule-x", "rule-a"],
                    }
                ],
            )
        ]
    )

    assert metrics["schema_success_rate"] == pytest.approx(1.0)
    assert metrics["repair_rate"] == pytest.approx(0.0)
    assert metrics["retrieval_recall_at_3"] == pytest.approx(1.0)
    assert metrics["retrieval_recall_at_5"] == pytest.approx(1.0)
    assert metrics["retrieval_mrr"] == pytest.approx(0.5)


def test_output_diff_has_every_v2_key() -> None:
    baseline = _case_result(
        expected_issues=[_issue("改善睡眠", "rule-a", confidence=0.7)],
        observed_issues=[_issue("改善睡眠", "rule-a", confidence=0.7)],
    )
    candidate = _case_result(
        expected_issues=[_issue("改善睡眠", "rule-a", confidence=0.7)],
        observed_issues=[_issue("治疗失眠", "rule-b", RiskLevel.HIGH, confidence=0.9)],
        observed_risk_level=RiskLevel.HIGH,
        review_required=True,
    )

    diff = build_output_diff(baseline=baseline, candidate=candidate)

    assert set(diff.model_dump()) == {
        "added_issues",
        "removed_issues",
        "changed_evidence_spans",
        "risk_level_changed",
        "rule_ids_changed",
        "confidence_changed",
        "rewrite_changed",
        "review_decision_changed",
    }
    assert diff.risk_level_changed is True
    assert diff.rule_ids_changed is True
    assert diff.confidence_changed is True
    assert diff.review_decision_changed is True
