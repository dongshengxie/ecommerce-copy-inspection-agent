from __future__ import annotations

from dataclasses import dataclass

from contracts.models import Issue
from llm.models import SemanticSkillResult


@dataclass(frozen=True)
class FusionResult:
    """The deterministic-first Issue set and any required-review signals."""

    issues: list[Issue]
    review_required: bool
    review_reasons: list[str]
    degradation_flags: list[str]


def fuse_issues(
    deterministic_issues: list[Issue], semantic_result: SemanticSkillResult
) -> FusionResult:
    """Keep deterministic results authoritative and surface semantic conflicts for review."""
    issues = list(deterministic_issues)
    review_reasons: list[str] = []
    for semantic_issue in semantic_result.issues:
        matching_tool_issue = next(
            (
                issue
                for issue in deterministic_issues
                if issue.field == semantic_issue.field
                and set(issue.rule_ids).intersection(semantic_issue.rule_ids)
            ),
            None,
        )
        if matching_tool_issue is None:
            issues.append(semantic_issue)
        elif (
            matching_tool_issue.evidence_span == semantic_issue.evidence_span
            and matching_tool_issue.risk_level == semantic_issue.risk_level
        ):
            merged_sources = list(dict.fromkeys(matching_tool_issue.source + semantic_issue.source))
            issues[issues.index(matching_tool_issue)] = matching_tool_issue.model_copy(
                update={"source": merged_sources}
            )
        else:
            review_reasons.append("Tool/Rule/LLM 结论冲突")

    for flag in semantic_result.degradation_flags:
        review_reasons.append(
            {
                "llm_failed": "LLM 调用失败",
                "structured_output_invalid": "Structured Output 校验失败",
            }.get(flag, flag)
        )
    return FusionResult(
        issues=issues,
        review_required=semantic_result.review_required or bool(review_reasons),
        review_reasons=list(dict.fromkeys(review_reasons)),
        degradation_flags=semantic_result.degradation_flags,
    )
