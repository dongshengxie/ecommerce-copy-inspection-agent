from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from contracts.models import Rule
from db.models.core import InspectionTaskRuleModel, QualityRuleModel


@dataclass(frozen=True)
class RulePublication:
    """The database-side outcome of publishing one complete rule baseline."""

    imported_count: int
    retired_count: int


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

    def publish_rules(self, rules: list[Rule]) -> RulePublication:
        """Activate the supplied complete baseline and retire superseded active versions.

        Historical rows remain intact for task-rule evidence lookup; only their active
        status changes, so newly created inspections load exactly this baseline.
        """
        imported_count = self.import_rules(rules)
        categories = {rule.category for rule in rules}
        active_versions = {
            (rule.rule_id, rule.version) for rule in rules if rule.status == "enabled"
        }
        retired_count = 0
        if categories:
            active_records = self._session.scalars(
                select(QualityRuleModel).where(
                    QualityRuleModel.category.in_(categories),
                    QualityRuleModel.status == "enabled",
                )
            ).all()
            for record in active_records:
                if (record.rule_id, record.version) not in active_versions:
                    record.status = "disabled"
                    retired_count += 1
        self._session.flush()
        return RulePublication(imported_count=imported_count, retired_count=retired_count)

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

    def list_by_task_rule_references(
        self, task_id: str, rule_ids: set[str] | None = None
    ) -> list[Rule]:
        """Load only the historically recorded rule ID/version pairs for one task."""
        if rule_ids == set():
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
            )
        )
        if rule_ids is not None:
            statement = statement.where(InspectionTaskRuleModel.rule_id.in_(rule_ids))
        statement = statement.order_by(QualityRuleModel.rule_id, QualityRuleModel.version)
        records = self._session.scalars(statement).all()
        return [Rule.model_validate(record.content_json) for record in records]
