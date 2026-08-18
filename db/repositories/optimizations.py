from __future__ import annotations

from sqlalchemy.orm import Session

from contracts.optimization import OptimizationResult
from db.models.core import OptimizationAttemptModel


class OptimizationRepository:
    """Persist explicit optimization outcomes without changing source inspections."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create_attempt(self, result: OptimizationResult) -> OptimizationAttemptModel:
        attempt = OptimizationAttemptModel(
            id=result.optimization_id,
            source_task_id=result.source_task_id,
            status=result.status.value,
            requested_fields=list(result.requested_fields),
            optimized_fields_json=result.optimized_fields,
            referenced_issues_json=[
                reference.model_dump(mode="json") for reference in result.referenced_issues
            ],
            referenced_rule_ids=result.referenced_rule_ids,
            verification_report_json=(
                result.verification_report.model_dump(mode="json")
                if result.verification_report is not None
                else None
            ),
            failure_reason=result.failure_reason,
        )
        self._session.add(attempt)
        self._session.flush()
        return attempt
