from __future__ import annotations

import httpx
from elasticsearch import Elasticsearch
from sqlalchemy.orm import Session, sessionmaker

from agent.graph.food_inspection_workflow import FoodInspectionWorkflow
from agent.state.inspection import SemanticInspectionSkill
from app.config import Settings
from contracts.models import InspectionReport, ProductInput, TraceEvent
from db.repositories.inspections import InspectionRepository
from db.repositories.rules import RuleRepository
from llm.copy_optimization import CopyOptimizationSkill
from llm.models import SemanticSkillResult
from llm.providers import DeepSeekProvider
from llm.semantic_risk import SemanticInspectionSkill as BoundedSemanticInspectionSkill
from llm.semantic_risk import SemanticRiskSkill
from rag.providers import SiliconFlowEmbeddingProvider, SiliconFlowRerankerProvider
from rag.retriever import RuleRetriever
from skills.food.quality import FoodQualitySkill


class _UnavailableSemanticInspectionSkill:
    """Make missing external-model configuration explicit and review-required."""

    def __init__(self, degradation_flag: str) -> None:
        self._degradation_flag = degradation_flag

    def inspect(
        self, product: ProductInput, rules: list[object], deterministic_issues: list[object]
    ) -> SemanticSkillResult:
        del product, rules, deterministic_issues
        return SemanticSkillResult(
            degradation_flags=[self._degradation_flag],
            review_required=True,
            trace_metadata={"error_category": self._degradation_flag},
        )


def create_semantic_inspection_skill(settings: Settings) -> SemanticInspectionSkill:
    """Assemble RAG and LLM dependencies only at the application boundary."""
    if not settings.bge_api_base_url or not settings.bge_api_key:
        return _UnavailableSemanticInspectionSkill("rag_unavailable")
    if not settings.deepseek_api_key:
        return _UnavailableSemanticInspectionSkill("llm_failed")

    http_client = httpx.Client()
    rule_retriever = RuleRetriever(
        client=Elasticsearch(settings.elasticsearch_url),
        embedding_provider=SiliconFlowEmbeddingProvider(
            client=http_client,
            base_url=settings.bge_api_base_url,
            api_key=settings.bge_api_key,
            model=settings.bge_embedding_model,
        ),
        reranker_provider=SiliconFlowRerankerProvider(
            client=http_client,
            base_url=settings.bge_api_base_url,
            api_key=settings.bge_api_key,
            model=settings.bge_reranker_model,
        ),
        index_name=f"{settings.elasticsearch_index_prefix}_v1",
    )
    return BoundedSemanticInspectionSkill(
        rule_retriever=rule_retriever,
        semantic_risk_skill=SemanticRiskSkill(
            llm_provider=DeepSeekProvider(
                client=http_client,
                api_key=settings.deepseek_api_key,
                model=settings.deepseek_model,
            ),
            prompt_version="1.1.0",
        ),
    )


def create_copy_optimization_skill(settings: Settings) -> CopyOptimizationSkill | None:
    """Create the isolated copy-generation dependency at the application boundary."""
    if not settings.deepseek_api_key:
        return None
    return CopyOptimizationSkill(
        llm_provider=DeepSeekProvider(
            client=httpx.Client(),
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
        ),
        prompt_version="1.0.0",
    )


class InspectionApplicationService:
    """Run the confirmed Phase 2 synchronous food-inspection lifecycle."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        semantic_inspection_skill: SemanticInspectionSkill | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._food_quality_skill = FoodQualitySkill()
        self._semantic_inspection_skill = semantic_inspection_skill

    def create_inspection(
        self, product: ProductInput, *, semantic_enabled: bool = False
    ) -> InspectionReport:
        with self._session_factory() as session:
            repository = InspectionRepository(session)
            product_revision = repository.get_or_create_product_revision(product)
            task = repository.create_running_task(product_revision.id, product.trigger_source)
            session.commit()

        try:
            return self._complete_inspection(
                task.id,
                product,
                semantic_enabled=semantic_enabled,
            )
        except Exception as error:
            self._record_failure(task.id, error)
            raise

    def _complete_inspection(
        self, task_id: str, product: ProductInput, *, semantic_enabled: bool
    ) -> InspectionReport:
        with self._session_factory() as session:
            workflow = FoodInspectionWorkflow(
                rule_loader=RuleRepository(session).list_enabled_food_rules,
                food_quality_skill=self._food_quality_skill,
                semantic_inspection_skill=(
                    self._semantic_inspection_skill if semantic_enabled else None
                ),
            )
            result = workflow.invoke(task_id=task_id, product=product)
            InspectionRepository(session).complete_task(
                task_id,
                result.report,
                result.rule_version,
                result.trace_events,
                result.rules,
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
