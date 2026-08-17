from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from agent.graph.food_inspection_workflow import FoodInspectionWorkflow
from contracts.models import InspectionReport, ProductInput, TraceEvent
from db.repositories.inspections import InspectionRepository
from db.repositories.rules import RuleRepository
from skills.food.quality import FoodQualitySkill


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
            workflow = FoodInspectionWorkflow(
                rule_loader=RuleRepository(session).list_enabled_food_rules,
                food_quality_skill=self._food_quality_skill,
            )
            result = workflow.invoke(task_id=task_id, product=product)
            InspectionRepository(session).complete_task(
                task_id,
                result.report,
                result.rule_version,
                result.trace_events,
            )
            session.commit()
            return result.report

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
