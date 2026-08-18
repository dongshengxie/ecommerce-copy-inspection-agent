from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.models import ProductInput, RiskLevel, TaskStatus
from contracts.optimization import OptimizationStatus


class GoldenIssue(BaseModel):
    """An owner-provided expected Issue used only as evaluation Ground Truth."""

    model_config = ConfigDict(extra="forbid")

    field: str
    issue_type: str
    risk_level: RiskLevel
    evidence_span: str
    rule_ids: list[str]


class GoldenCase(BaseModel):
    """One versioned food Golden Dataset record without generating any labels."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    dataset_version: str
    input: ProductInput
    expected_issues: list[GoldenIssue] = Field(default_factory=list)
    expected_risk_level: RiskLevel
    expected_rule_ids: list[str] = Field(default_factory=list)
    notes: str


class NormalizedIssue(BaseModel):
    """The stable comparison projection for an expected or observed Issue."""

    model_config = ConfigDict(extra="forbid")

    field: str
    rule_ids: list[str]
    evidence_span: str
    risk_level: RiskLevel
    confidence: float | None = None


class EvidenceSpanChange(BaseModel):
    """A same-rule comparison whose reported source span has changed."""

    model_config = ConfigDict(extra="forbid")

    field: str
    rule_ids: list[str]
    previous_evidence_span: str
    current_evidence_span: str


class OutputDiff(BaseModel):
    """The fixed V2 comparison shape for a candidate against a baseline output."""

    model_config = ConfigDict(extra="forbid")

    added_issues: list[NormalizedIssue] = Field(default_factory=list)
    removed_issues: list[NormalizedIssue] = Field(default_factory=list)
    changed_evidence_spans: list[EvidenceSpanChange] = Field(default_factory=list)
    risk_level_changed: bool = False
    rule_ids_changed: bool = False
    confidence_changed: bool = False
    rewrite_changed: bool = False
    review_decision_changed: bool = False


class EvaluationCaseResult(BaseModel):
    """Safe, normalized result of executing one Golden Case."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    task_status: TaskStatus
    expected_risk_level: RiskLevel
    observed_risk_level: RiskLevel
    expected_issues: list[NormalizedIssue] = Field(default_factory=list)
    observed_issues: list[NormalizedIssue] = Field(default_factory=list)
    expected_rule_ids: list[str] = Field(default_factory=list)
    observed_rule_ids: list[str] = Field(default_factory=list)
    review_required: bool
    degradation_flags: list[str] = Field(default_factory=list)
    latency_ms: int = Field(ge=0)
    semantic_metadata: list[dict[str, object]] = Field(default_factory=list)
    observed_evidence_grounded: list[bool] = Field(default_factory=list)
    optimization_status: OptimizationStatus | None = None
    protected_fact_preserved: bool | None = None
    new_risk_introduced: bool | None = None
    rewrite_changed: bool = False
    expected_diff: OutputDiff | None = None
    baseline_diff: OutputDiff | None = None


class EvaluationRunResult(BaseModel):
    """A serializable, privacy-safe aggregation of one evaluation run."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["offline", "live"]
    dataset_version: str
    versions: dict[str, str | None]
    metrics: dict[str, float | None]
    case_results: list[EvaluationCaseResult]
    failure_summary: dict[str, int] = Field(default_factory=dict)
