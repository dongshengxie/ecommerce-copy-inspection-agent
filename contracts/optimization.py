from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from contracts.models import InspectionReport

WritableCopyField = Literal[
    "title",
    "selling_points",
    "description",
    "marketing_description",
]


class OptimizationRequest(BaseModel):
    """A user-selected set of food copy fields eligible for optimization."""

    model_config = ConfigDict(extra="forbid")

    fields: list[WritableCopyField] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def fields_must_be_unique(self) -> OptimizationRequest:
        if len(self.fields) != len(set(self.fields)):
            raise ValueError("优化字段不能重复")
        return self


class OptimizationStatus(StrEnum):
    SUCCESS = "success"
    VERIFICATION_FAILED = "verification_failed"
    FAILED = "failed"


class OptimizationIssueReference(BaseModel):
    """A source Issue reference without altering the frozen Issue Contract."""

    model_config = ConfigDict(extra="forbid")

    field: str
    evidence_span: str
    rule_ids: list[str]


class OptimizationResult(BaseModel):
    """The immutable outcome of one explicitly requested optimization attempt."""

    model_config = ConfigDict(extra="forbid")

    optimization_id: str
    source_task_id: str
    status: OptimizationStatus
    requested_fields: list[WritableCopyField]
    optimized_fields: dict[WritableCopyField, str | list[str]] = Field(default_factory=dict)
    referenced_issues: list[OptimizationIssueReference] = Field(default_factory=list)
    referenced_rule_ids: list[str] = Field(default_factory=list)
    verification_report: InspectionReport | None = None
    failure_reason: str | None = None
