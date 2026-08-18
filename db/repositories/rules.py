from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from contracts.models import Rule
from db.models.core import InspectionTaskRuleModel, QualityRuleModel


class RuleRepository:
    """Access the imported, versioned quality-rule records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def import_rules(self, rules: list[Rule]) -> int:
        """Add previously unseen (rule_id, version) records without committing."""
        imported_count = 0
        for rule in rules:
            existing = self._session.scalar(
                select(QualityRuleModel.id).where(
                    QualityRuleModel.rule_id == rule.rule_id,
                    QualityRuleModel.version == rule.version,
                )
            )
            if existing is not None:
                continue

            self._session.add(
                QualityRuleModel(
                    id=str(uuid4()),
                    rule_id=rule.rule_id,
                    version=rule.version,
                    category=rule.category,
                    status=rule.status,
                    effective_at=rule.effective_at,
                    content_json=rule.model_dump(mode="json"),
                )
            )
            imported_count += 1
        self._session.flush()
        return imported_count

    def list_enabled_food_rules(self) -> list[Rule]:
        """Return only enabled food rules in stable Rule ID order."""
        statement = (
            select(QualityRuleModel)
            .where(
                QualityRuleModel.category == "食品",
                QualityRuleModel.status == "enabled",
            )
            .order_by(QualityRuleModel.rule_id)
        )
        records = self._session.scalars(statement).all()
        return [Rule.model_validate(record.content_json) for record in records]

    def list_by_task_rule_references(self, task_id: str, rule_ids: set[str]) -> list[Rule]:
        """Load only the historically recorded rule ID/version pairs for one task."""
        if not rule_ids:
            return []
        statement = (
            select(QualityRuleModel)
            .join(
                InspectionTaskRuleModel,
                (InspectionTaskRuleModel.rule_id == QualityRuleModel.rule_id)
                & (InspectionTaskRuleModel.rule_version == QualityRuleModel.version),
            )
            .where(
                InspectionTaskRuleModel.task_id == task_id,
                InspectionTaskRuleModel.rule_id.in_(rule_ids),
            )
            .order_by(QualityRuleModel.rule_id, QualityRuleModel.version)
        )
        records = self._session.scalars(statement).all()
        return [Rule.model_validate(record.content_json) for record in records]
