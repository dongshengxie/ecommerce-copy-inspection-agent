from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from operator import add
from typing import Annotated, Required, TypedDict

from contracts.models import (
    InspectionReport,
    ProductInput,
    RiskLevel,
    Rule,
    SkillResult,
    TraceEvent,
)

RuleLoader = Callable[[], list[Rule]]


class InspectionState(TypedDict, total=False):
    task_id: Required[str]
    product: Required[ProductInput]
    rules: list[Rule]
    skill_result: SkillResult
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
