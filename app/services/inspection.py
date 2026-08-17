from __future__ import annotations

from time import perf_counter

from sqlalchemy.orm import Session, sessionmaker

from contracts.models import InspectionReport, ProductInput, RiskLevel, TaskStatus, TraceEvent
from db.repositories.inspections import InspectionRepository
from db.repositories.rules import RuleRepository
from skills.food.quality import FoodQualitySkill
from tools.food.risk import aggregate_risk


class InspectionApplicationService:
    """Run the confirmed Phase 2 synchronous food-inspection lifecycle."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._food_quality_skill = FoodQualitySkill()

    def create_inspection(self, product: ProductInput) -> InspectionReport:
        with self._session_factory() as session:
            repository = InspectionRepository(session)
            product_revision = repository.get_or_create_product_revision(product)
            task = repository.create_running_task(product_revision.id, product.trigger_source)
            session.commit()

        try:
            return self._complete_inspection(task.id, product)
        except Exception as error:
            self._record_failure(task.id, error)
            raise

    def _complete_inspection(self, task_id: str, product: ProductInput) -> InspectionReport:
        with self._session_factory() as session:
            rules = RuleRepository(session).list_enabled_food_rules()
            started_at = perf_counter()
            skill_result = self._food_quality_skill.inspect(product, rules)
            skill_latency_ms = int((perf_counter() - started_at) * 1000)
            automated_risk_level = aggregate_risk(skill_result.issues)
            review_required = automated_risk_level is RiskLevel.HIGH
            trace_id = str(task_id)
            report = InspectionReport(
                task_id=task_id,
                status=TaskStatus.SUCCESS,
                automated_risk_level=automated_risk_level,
                review_required=review_required,
                review_reasons=["命中 high 风险"] if review_required else [],
                issues=skill_result.issues,
                trace_id=trace_id,
            )
            rule_version = ",".join(sorted({rule.version for rule in rules}))
            traces = [
                TraceEvent(
                    task_id=task_id,
                    step_name="food_quality_skill",
                    tool_or_skill_name=skill_result.name,
                    rule_ids=sorted(
                        {rule_id for issue in skill_result.issues for rule_id in issue.rule_ids}
                    ),
                    decision=f"生成 {len(skill_result.issues)} 个确定性 Issue",
                    status="success",
                    latency_ms=skill_latency_ms,
                ),
                TraceEvent(
                    task_id=task_id,
                    step_name="risk_aggregator",
                    tool_or_skill_name="aggregate_risk",
                    rule_ids=[],
                    decision=f"自动风险等级为 {automated_risk_level.value}",
                    status="success",
                    latency_ms=0,
                ),
            ]
            InspectionRepository(session).complete_task(task_id, report, rule_version, traces)
            session.commit()
            return report

    def _record_failure(self, task_id: str, error: Exception) -> None:
        with self._session_factory() as session:
            trace = TraceEvent(
                task_id=task_id,
                step_name="inspection_failure",
                tool_or_skill_name="inspection_application_service",
                decision="同步质检执行失败",
                status="failed",
                latency_ms=0,
                error=str(error),
            )
            InspectionRepository(session).fail_task(task_id, error, trace)
            session.commit()
