from __future__ import annotations

from collections import Counter
from math import ceil

from contracts.models import Issue, RiskLevel, TaskStatus
from contracts.optimization import OptimizationStatus
from evaluation.models import (
    EvaluationCaseResult,
    EvidenceSpanChange,
    NormalizedIssue,
    OutputDiff,
)

IssueKey = tuple[str, tuple[str, ...], str, RiskLevel]
IssueCoreKey = tuple[str, tuple[str, ...], RiskLevel]


def normalize_issue(issue: Issue) -> NormalizedIssue:
    """Convert an Issue-like object into the frozen comparison projection."""
    return NormalizedIssue(
        field=issue.field,
        rule_ids=sorted(issue.rule_ids),
        evidence_span=issue.evidence_span,
        risk_level=issue.risk_level,
        confidence=issue.confidence,
    )


def build_output_diff(
    *, baseline: EvaluationCaseResult, candidate: EvaluationCaseResult
) -> OutputDiff:
    """Compare candidate output with an optional baseline, never with owner labels."""
    baseline_counts = Counter(_issue_key(issue) for issue in baseline.observed_issues)
    candidate_counts = Counter(_issue_key(issue) for issue in candidate.observed_issues)
    added_keys = candidate_counts - baseline_counts
    removed_keys = baseline_counts - candidate_counts
    return OutputDiff(
        added_issues=_issues_from_counts(candidate.observed_issues, added_keys),
        removed_issues=_issues_from_counts(baseline.observed_issues, removed_keys),
        changed_evidence_spans=_changed_evidence_spans(
            baseline.observed_issues, candidate.observed_issues
        ),
        risk_level_changed=baseline.observed_risk_level != candidate.observed_risk_level,
        rule_ids_changed=set(baseline.observed_rule_ids) != set(candidate.observed_rule_ids),
        confidence_changed=_confidence_map(baseline.observed_issues)
        != _confidence_map(candidate.observed_issues),
        rewrite_changed=baseline.rewrite_changed != candidate.rewrite_changed,
        review_decision_changed=baseline.review_required != candidate.review_required,
    )


def compute_metrics(case_results: list[EvaluationCaseResult]) -> dict[str, float | None]:
    """Compute deterministic V2 metrics; every absent denominator remains null."""
    expected_counts: Counter[IssueKey] = Counter()
    observed_counts: Counter[IssueKey] = Counter()
    expected_high_counts: Counter[IssueKey] = Counter()
    expected_rule_ids: set[str] = set()
    observed_rule_ids: set[str] = set()
    evidence_grounded: list[bool] = []
    latencies: list[int] = []
    schema_values: list[bool] = []
    repair_values: list[bool] = []
    retrieval_ranks: list[int | None] = []

    for result in case_results:
        expected_counts.update(_issue_key(issue) for issue in result.expected_issues)
        observed_counts.update(_issue_key(issue) for issue in result.observed_issues)
        expected_high_counts.update(
            _issue_key(issue)
            for issue in result.expected_issues
            if issue.risk_level is RiskLevel.HIGH
        )
        expected_rule_ids.update(result.expected_rule_ids)
        observed_rule_ids.update(result.observed_rule_ids)
        evidence_grounded.extend(result.observed_evidence_grounded)
        latencies.append(result.latency_ms)
        _append_semantic_metrics(result, schema_values, repair_values, retrieval_ranks)

    matched_counts = expected_counts & observed_counts
    matched_high_counts = expected_high_counts & observed_counts
    matched_count = sum(matched_counts.values())
    expected_count = sum(expected_counts.values())
    observed_count = sum(observed_counts.values())
    added_observed_count = sum((observed_counts - expected_counts).values())
    expected_high_count = sum(expected_high_counts.values())

    risk_matches = sum(
        result.expected_risk_level is result.observed_risk_level for result in case_results
    )
    successful_tasks = sum(result.task_status is TaskStatus.SUCCESS for result in case_results)
    degraded_tasks = sum(bool(result.degradation_flags) for result in case_results)
    optimization_results = [
        result for result in case_results if result.optimization_status is not None
    ]
    protected_fact_results = [
        result for result in case_results if result.protected_fact_preserved is not None
    ]
    new_risk_results = [result for result in case_results if result.new_risk_introduced is not None]

    precision = _ratio(matched_count, observed_count)
    recall = _ratio(matched_count, expected_count)
    return {
        "risk_level_accuracy": _ratio(risk_matches, len(case_results)),
        "issue_precision": precision,
        "issue_recall": recall,
        "issue_f1": _f1(precision, recall),
        "false_positive_rate": _ratio(added_observed_count, observed_count),
        "high_risk_recall": _ratio(sum(matched_high_counts.values()), expected_high_count),
        "rule_citation_precision": _ratio(
            len(expected_rule_ids & observed_rule_ids), len(observed_rule_ids)
        ),
        "rule_citation_recall": _ratio(
            len(expected_rule_ids & observed_rule_ids), len(expected_rule_ids)
        ),
        "evidence_grounded_rate": _ratio(sum(evidence_grounded), len(evidence_grounded)),
        "task_success_rate": _ratio(successful_tasks, len(case_results)),
        "degradation_rate": _ratio(degraded_tasks, len(case_results)),
        "mean_latency_ms": _mean(latencies),
        "p95_latency_ms": _p95(latencies),
        "schema_success_rate": _ratio(sum(schema_values), len(schema_values)),
        "repair_rate": _ratio(sum(repair_values), len(repair_values)),
        "retrieval_recall_at_3": _ratio(
            sum(rank is not None and rank <= 3 for rank in retrieval_ranks),
            len(retrieval_ranks),
        ),
        "retrieval_recall_at_5": _ratio(
            sum(rank is not None and rank <= 5 for rank in retrieval_ranks),
            len(retrieval_ranks),
        ),
        "retrieval_mrr": _mean([0.0 if rank is None else 1.0 / rank for rank in retrieval_ranks]),
        "rewrite_pass_rate": _ratio(
            sum(
                result.optimization_status is OptimizationStatus.SUCCESS
                for result in optimization_results
            ),
            len(optimization_results),
        ),
        "protected_fact_preservation_rate": _ratio(
            sum(result.protected_fact_preserved is True for result in protected_fact_results),
            len(protected_fact_results),
        ),
        "new_risk_introduction_rate": _ratio(
            sum(result.new_risk_introduced is True for result in new_risk_results),
            len(new_risk_results),
        ),
    }


def _append_semantic_metrics(
    result: EvaluationCaseResult,
    schema_values: list[bool],
    repair_values: list[bool],
    retrieval_ranks: list[int | None],
) -> None:
    candidates: list[str] | None = None
    for metadata in result.semantic_metadata:
        schema_valid = metadata.get("schema_valid")
        repair_attempted = metadata.get("repair_attempted")
        if isinstance(schema_valid, bool):
            schema_values.append(schema_valid)
            repair_values.append(repair_attempted if isinstance(repair_attempted, bool) else False)
        candidate_rule_ids = metadata.get("candidate_rule_ids")
        if isinstance(candidate_rule_ids, list) and all(
            isinstance(rule_id, str) for rule_id in candidate_rule_ids
        ):
            candidates = candidate_rule_ids
    if candidates is not None and result.expected_rule_ids:
        for rule_id in result.expected_rule_ids:
            retrieval_ranks.append(candidates.index(rule_id) + 1 if rule_id in candidates else None)


def _issue_key(issue: NormalizedIssue) -> IssueKey:
    return (
        issue.field,
        tuple(sorted(issue.rule_ids)),
        issue.evidence_span,
        issue.risk_level,
    )


def _issue_core_key(issue: NormalizedIssue) -> IssueCoreKey:
    return issue.field, tuple(sorted(issue.rule_ids)), issue.risk_level


def _issues_from_counts(
    issues: list[NormalizedIssue], counts: Counter[IssueKey]
) -> list[NormalizedIssue]:
    output: list[NormalizedIssue] = []
    remaining = counts.copy()
    for issue in issues:
        key = _issue_key(issue)
        if remaining[key] > 0:
            output.append(issue)
            remaining[key] -= 1
    return output


def _changed_evidence_spans(
    baseline: list[NormalizedIssue], candidate: list[NormalizedIssue]
) -> list[EvidenceSpanChange]:
    baseline_by_core = {_issue_core_key(issue): issue for issue in baseline}
    changes: list[EvidenceSpanChange] = []
    for issue in candidate:
        previous = baseline_by_core.get(_issue_core_key(issue))
        if previous is not None and previous.evidence_span != issue.evidence_span:
            changes.append(
                EvidenceSpanChange(
                    field=issue.field,
                    rule_ids=issue.rule_ids,
                    previous_evidence_span=previous.evidence_span,
                    current_evidence_span=issue.evidence_span,
                )
            )
    return changes


def _confidence_map(issues: list[NormalizedIssue]) -> dict[IssueKey, float | None]:
    return {_issue_key(issue): issue.confidence for issue in issues}


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def _mean(values: list[int] | list[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def _p95(values: list[int]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return float(ordered[ceil(len(ordered) * 0.95) - 1])
