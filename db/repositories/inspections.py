from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from contracts.models import InspectionReport, ProductInput, Rule, TaskStatus, TraceEvent
from db.models.core import (
    AgentTraceModel,
    InspectionIssueModel,
    InspectionResultModel,
    InspectionTaskModel,
    InspectionTaskRuleModel,
    ProductModel,
    ProductRevisionModel,
)

SAFE_TRACE_METADATA_KEYS = frozenset(
    {
        "strategy",
        "candidate_rule_ids",
        "index_name",
        "provider",
        "prompt_name",
        "prompt_version",
        "model_name",
        "input_tokens",
        "output_tokens",
        "latency_ms",
        "retry_count",
        "schema_valid",
        "repair_attempted",
        "operation",
        "attempt",
        "error_category",
    }
)


class InspectionRepository:
    """Persist synchronous inspection task lifecycle records without committing."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create_product_revision(self, product: ProductInput) -> ProductRevisionModel:
        product_record = self._session.get(ProductModel, product.product_id)
        if product_record is None:
            self._session.add(
                ProductModel(product_id=product.product_id, category=product.category)
            )

        payload = product.model_dump(mode="json")
        content_hash = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        ).hexdigest()
        existing_revision = self._session.scalar(
            select(ProductRevisionModel).where(
                ProductRevisionModel.product_id == product.product_id,
                ProductRevisionModel.revision == product.product_revision,
            )
        )
        if existing_revision is not None:
            if existing_revision.content_hash != content_hash:
                raise ValueError("同一商品修订号对应的内容不一致")
            return existing_revision

        revision_record = ProductRevisionModel(
            id=str(uuid4()),
            product_id=product.product_id,
            revision=product.product_revision,
            content_hash=content_hash,
            payload_json=payload,
        )
        self._session.add(revision_record)
        self._session.flush()
        return revision_record

    def create_running_task(
        self, product_revision_id: str, trigger_source: str
    ) -> InspectionTaskModel:
        task = InspectionTaskModel(
            id=str(uuid4()),
            product_revision_id=product_revision_id,
            status=TaskStatus.RUNNING.value,
            trigger_source=trigger_source,
            rule_version="pending",
        )
        self._session.add(task)
        self._session.flush()
        return task

    def complete_task(
        self,
        task_id: str,
        report: InspectionReport,
        rule_version: str,
        traces: list[TraceEvent],
        rules: list[Rule],
    ) -> None:
        task = self._require_task(task_id)
        task.status = TaskStatus.SUCCESS.value
        task.rule_version = rule_version
        task.error_message = None
        self._session.add(
            InspectionResultModel(
                task_id=task_id,
                automated_risk_level=report.automated_risk_level.value,
                report_json=report.model_dump(mode="json"),
                review_required=report.review_required,
                degradation_flags=report.degradation_flags,
            )
        )
        for issue in report.issues:
            self._session.add(
                InspectionIssueModel(
                    id=str(uuid4()),
                    task_id=task_id,
                    field=issue.field,
                    issue_type=issue.issue_type,
                    risk_level=issue.risk_level.value,
                    evidence_span=issue.evidence_span,
                    rule_ids=issue.rule_ids,
                    sources=issue.source,
                    confidence=issue.confidence,
                )
            )
        self._add_task_rule_references(task_id, rules)
        self._add_traces(traces)
        self._session.flush()

    def fail_task(self, task_id: str, error: Exception, trace: TraceEvent) -> None:
        task = self._require_task(task_id)
        task.status = TaskStatus.FAILED.value
        task.error_message = str(error)
        self._add_traces([trace])
        self._session.flush()

    def get_task(self, task_id: str) -> InspectionTaskModel | None:
        return self._session.get(InspectionTaskModel, task_id)

    def get_report(self, task_id: str) -> InspectionReport | None:
        result = self._session.get(InspectionResultModel, task_id)
        if result is None:
            return None
        return InspectionReport.model_validate(result.report_json)

    def get_task_rule_references(self, task_id: str) -> list[InspectionTaskRuleModel]:
        return list(
            self._session.scalars(
                select(InspectionTaskRuleModel)
                .where(InspectionTaskRuleModel.task_id == task_id)
                .order_by(InspectionTaskRuleModel.rule_id, InspectionTaskRuleModel.rule_version)
            )
        )

    def list_trace_summaries(self, task_id: str) -> list[dict[str, object]]:
        """Return only API-safe trace fields, excluding raw inputs and model outputs."""
        traces = self._session.scalars(
            select(AgentTraceModel).where(AgentTraceModel.task_id == task_id)
        )
        return [
            {
                "step_name": trace.step_name,
                "tool_or_skill_name": trace.tool_or_skill_name,
                "rule_ids": trace.rule_ids,
                "decision": trace.decision,
                "status": trace.status,
                "latency_ms": trace.latency_ms,
                "metadata": {
                    key: value
                    for key, value in trace.metadata_json.items()
                    if key in SAFE_TRACE_METADATA_KEYS
                },
            }
            for trace in traces
        ]

    def _require_task(self, task_id: str) -> InspectionTaskModel:
        task = self._session.get(InspectionTaskModel, task_id)
        if task is None:
            raise LookupError(f"未知质检任务：{task_id}")
        return task

    def _add_task_rule_references(self, task_id: str, rules: list[Rule]) -> None:
        for rule_id, rule_version in sorted({(rule.rule_id, rule.version) for rule in rules}):
            self._session.add(
                InspectionTaskRuleModel(
                    task_id=task_id,
                    rule_id=rule_id,
                    rule_version=rule_version,
                )
            )

    def _add_traces(self, traces: list[TraceEvent]) -> None:
        for trace in traces:
            self._session.add(
                AgentTraceModel(
                    id=str(uuid4()),
                    task_id=trace.task_id,
                    step_name=trace.step_name,
                    tool_or_skill_name=trace.tool_or_skill_name,
                    rule_ids=trace.rule_ids,
                    decision=trace.decision,
                    status=trace.status,
                    latency_ms=trace.latency_ms,
                    error_message=trace.error,
                    metadata_json=trace.metadata,
                )
            )
