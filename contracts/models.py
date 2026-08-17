from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RiskLevel(StrEnum):
    PASS = "pass"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class FoodAttributes(BaseModel):
    model_config = ConfigDict(extra="allow")

    ingredients: str
    shelf_life: str
    storage_method: str
    origin: str
    applicable_people: str | None = None
    net_content: str | None = None
    brand: str | None = None


class ProductInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: str = Field(min_length=1)
    product_revision: int = Field(ge=1)
    category: Literal["食品"]
    title: str
    selling_points: list[str]
    description: str
    attributes: FoodAttributes
    marketing_description: str
    trigger_source: str = Field(min_length=1)


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    category: Literal["食品"]
    field_scope: list[str] = Field(min_length=1)
    issue_type: str = Field(min_length=1)
    risk_level: RiskLevel
    rule_strength: str = Field(min_length=1)
    rule_text: str = Field(min_length=1)
    bad_examples: list[str]
    rewrite_hint: str = Field(min_length=1)
    status: Literal["draft", "enabled", "disabled", "expired"]
    effective_at: str = Field(min_length=1)


class Issue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1)
    issue_type: str = Field(min_length=1)
    risk_level: RiskLevel
    evidence_span: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    rule_ids: list[str]
    source: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    suggestion: str = Field(min_length=1)


class ToolResult(BaseModel):
    name: str
    status: Literal["success", "failed", "skipped"]
    issues: list[Issue] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    trace_refs: list[str] = Field(default_factory=list)


class SkillResult(ToolResult):
    pass


class TraceEvent(BaseModel):
    task_id: str
    step_name: str
    tool_or_skill_name: str
    rule_ids: list[str] = Field(default_factory=list)
    decision: str
    status: Literal["success", "failed"]
    latency_ms: int = Field(ge=0)
    error: str | None = None


class InspectionReport(BaseModel):
    task_id: str
    status: TaskStatus
    automated_risk_level: RiskLevel
    review_required: bool
    review_reasons: list[str] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    degradation_flags: list[str] = Field(default_factory=list)
    trace_id: str
