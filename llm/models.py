from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field

from contracts.models import Issue


class SemanticFinding(BaseModel):
    """One LLM-proposed finding that must be reconciled with a retrieved Rule."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str = Field(min_length=1)
    rule_version: str = Field(min_length=1)
    field: str = Field(min_length=1)
    evidence_span: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


@dataclass(frozen=True)
class LLMResponse:
    """Parsed structured output and safe call metadata, without raw model text."""

    payload: dict[str, object]
    model_name: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


@dataclass(frozen=True)
class SemanticSkillResult:
    """Semantic issues and recoverable-degradation data for fixed workflow fusion."""

    issues: list[Issue] = field(default_factory=list)
    degradation_flags: list[str] = field(default_factory=list)
    review_required: bool = False
    trace_metadata: dict[str, object] = field(default_factory=dict)
