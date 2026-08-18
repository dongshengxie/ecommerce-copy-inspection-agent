from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from operator import add
from typing import Annotated, Protocol, Required, TypedDict

from contracts.models import (
    InspectionReport,
    Issue,
    ProductInput,
    RiskLevel,
    Rule,
    SkillResult,
    TraceEvent,
)
from llm.models import SemanticSkillResult

RuleLoader = Callable[[], list[Rule]]


class SemanticInspectionSkill(Protocol):
    """Run a bounded semantic pass after deterministic food checks."""

    def inspect(
        self,
        product: ProductInput,
        rules: list[Rule],
        deterministic_issues: list[Issue],
    ) -> SemanticSkillResult:
        """Return semantic findings or a review-required degradation result."""


class InspectionState(TypedDict, total=False):
    task_id: Required[str]
    product: Required[ProductInput]
    rules: list[Rule]
    skill_result: SkillResult
    semantic_result: SemanticSkillResult
    issues: list[Issue]
    degradation_flags: list[str]
    automated_risk_level: RiskLevel
    review_required: bool
    review_reasons: list[str]
    report: InspectionReport
    trace_events: Annotated[list[TraceEvent], add]


@dataclass(frozen=True)
class WorkflowResult:
    report: InspectionReport
    rule_version: str
    trace_events: list[TraceEvent]
