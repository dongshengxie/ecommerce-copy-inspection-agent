from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProductModel(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ProductRevisionModel(Base):
    __tablename__ = "product_revisions"
    __table_args__ = (UniqueConstraint("product_id", "revision", name="uq_product_revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.product_id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class QualityRuleModel(Base):
    __tablename__ = "quality_rules"
    __table_args__ = (UniqueConstraint("rule_id", "version", name="uq_rule_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_at: Mapped[str] = mapped_column(String(64), nullable=False)
    content_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class InspectionTaskModel(Base):
    __tablename__ = "inspection_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    product_revision_id: Mapped[str] = mapped_column(
        ForeignKey("product_revisions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_source: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class InspectionResultModel(Base):
    __tablename__ = "inspection_results"

    task_id: Mapped[str] = mapped_column(ForeignKey("inspection_tasks.id"), primary_key=True)
    automated_risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    report_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    review_required: Mapped[bool] = mapped_column(nullable=False)
    degradation_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class InspectionIssueModel(Base):
    __tablename__ = "inspection_issues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("inspection_tasks.id"), nullable=False)
    field: Mapped[str] = mapped_column(String(128), nullable=False)
    issue_type: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_span: Mapped[str] = mapped_column(Text, nullable=False)
    rule_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    sources: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)


class InspectionTaskRuleModel(Base):
    """The immutable rule ID/version set used by one completed inspection task."""

    __tablename__ = "inspection_task_rules"

    task_id: Mapped[str] = mapped_column(ForeignKey("inspection_tasks.id"), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    rule_version: Mapped[str] = mapped_column(String(64), primary_key=True)


class OptimizationAttemptModel(Base):
    """One explicit optimization outcome, separate from its source inspection report."""

    __tablename__ = "optimization_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_task_id: Mapped[str] = mapped_column(ForeignKey("inspection_tasks.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    optimized_fields_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    referenced_issues_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    referenced_rule_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    verification_report_json: Mapped[dict[str, object] | None] = mapped_column(JSON)
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class AgentTraceModel(Base):
    __tablename__ = "agent_traces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("inspection_tasks.id"), nullable=False)
    step_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_or_skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
