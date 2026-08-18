from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session, sessionmaker

from agent.graph.food_inspection_workflow import FoodInspectionWorkflow
from agent.state.inspection import SemanticInspectionSkill
from contracts.models import Issue, ProductInput, Rule, TaskStatus, TraceEvent
from contracts.optimization import (
    OptimizationIssueReference,
    OptimizationRequest,
    OptimizationResult,
    OptimizationStatus,
    WritableCopyField,
)
from db.repositories.inspections import InspectionRepository
from db.repositories.optimizations import OptimizationRepository
from db.repositories.rules import RuleRepository
from llm.copy_optimization import CopyOptimizationArtifact, CopyOptimizationSkill
from llm.models import SemanticSkillResult
from skills.food.quality import FoodQualitySkill


class OptimizationNotFoundError(LookupError):
    """The requested source inspection task or report does not exist."""


class OptimizationConflictError(ValueError):
    """The source task cannot be optimized under the explicit API Contract."""


class _UnavailableVerificationSemanticSkill:
    """Prevent an optimization from succeeding when semantic verification is unavailable."""

    def inspect(
        self, product: ProductInput, rules: list[Rule], deterministic_issues: list[Issue]
    ) -> SemanticSkillResult:
        del product, rules, deterministic_issues
        return SemanticSkillResult(
            degradation_flags=["semantic_verification_unavailable"],
            review_required=True,
            trace_metadata={"error_category": "semantic_verification_unavailable"},
        )


class OptimizationApplicationService:
    """Run explicit, bounded copy optimization without mutating source inspections."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        copy_optimization_skill: CopyOptimizationSkill | None,
        semantic_inspection_skill: SemanticInspectionSkill | None,
    ) -> None:
        self._session_factory = session_factory
        self._copy_optimization_skill = copy_optimization_skill
        self._semantic_inspection_skill = semantic_inspection_skill
        self._food_quality_skill = FoodQualitySkill()

    def optimize(self, task_id: str, request: OptimizationRequest) -> OptimizationResult:
        product, report, rules, source_issues = self._load_source(task_id, request)
        if self._copy_optimization_skill is None:
            artifact = CopyOptimizationArtifact(
                referenced_rule_ids=self._rule_ids(source_issues),
                failure_reason="llm_failed",
                safe_metadata={
                    "operation": "copy_optimization",
                    "error_category": "llm_failed",
                    "schema_valid": False,
                    "repair_attempted": False,
                    "retry_count": 0,
                },
            )
        else:
            artifact = self._copy_optimization_skill.optimize(product, report, rules, request)

        traces = [self._optimization_trace(task_id, artifact, attempt=1)]
        if artifact.failure_reason is not None:
            return self._persist(
                self._result(
                    task_id,
                    request,
                    source_issues,
                    artifact,
                    status=OptimizationStatus.FAILED,
                ),
                traces,
            )

        verification = self._verify(task_id, product, rules, artifact.optimized_fields)
        failure_reasons = self._verification_failure_reasons(
            report.issues, request.fields, verification.report
        )
        traces.append(
            self._verification_trace(task_id, verification.report, failure_reasons, attempt=1)
        )
        if not failure_reasons:
            return self._persist(
                self._result(
                    task_id,
                    request,
                    source_issues,
                    artifact,
                    status=OptimizationStatus.SUCCESS,
                    verification_report=verification.report,
                ),
                traces,
            )

        if self._copy_optimization_skill is None:
            return self._persist(
                self._result(
                    task_id,
                    request,
                    source_issues,
                    artifact,
                    status=OptimizationStatus.VERIFICATION_FAILED,
                    verification_report=verification.report,
                    failure_reason=self._failure_reason(failure_reasons),
                ),
                traces,
            )

        replacement = self._copy_optimization_skill.optimize(
            product,
            report,
            rules,
            request,
            failure_reasons=failure_reasons,
            previous_optimized_fields=artifact.optimized_fields,
        )
        traces.append(self._optimization_trace(task_id, replacement, attempt=2))
        if replacement.failure_reason is not None:
            return self._persist(
                self._result(
                    task_id,
                    request,
                    source_issues,
                    replacement,
                    status=OptimizationStatus.FAILED,
                    verification_report=verification.report,
                ),
                traces,
            )

        replacement_verification = self._verify(
            task_id, product, rules, replacement.optimized_fields
        )
        replacement_reasons = self._verification_failure_reasons(
            report.issues, request.fields, replacement_verification.report
        )
        traces.append(
            self._verification_trace(
                task_id,
                replacement_verification.report,
                replacement_reasons,
                attempt=2,
            )
        )
        return self._persist(
            self._result(
                task_id,
                request,
                source_issues,
                replacement,
                status=(
                    OptimizationStatus.SUCCESS
                    if not replacement_reasons
                    else OptimizationStatus.VERIFICATION_FAILED
                ),
                verification_report=replacement_verification.report,
                failure_reason=(
                    None if not replacement_reasons else self._failure_reason(replacement_reasons)
                ),
            ),
            traces,
        )

    def _load_source(
        self, task_id: str, request: OptimizationRequest
    ) -> tuple[ProductInput, object, list[Rule], list[Issue]]:
        with self._session_factory() as session:
            inspection_repository = InspectionRepository(session)
            task = inspection_repository.get_task(task_id)
            if task is None:
                raise OptimizationNotFoundError("质检任务不存在")
            if task.status != TaskStatus.SUCCESS.value:
                raise OptimizationConflictError("仅成功质检任务可执行文案优化")
            report = inspection_repository.get_report(task_id)
            product = inspection_repository.get_product_for_task(task_id)
            rules = RuleRepository(session).list_by_task_rule_references(task_id)
        if report is None or product is None:
            raise OptimizationNotFoundError("质检结果不存在")
        source_issues = [issue for issue in report.issues if issue.field in request.fields]
        if not source_issues:
            raise OptimizationConflictError("所选字段没有可优化的 Issue")
        return product, report, rules, source_issues

    def _verify(
        self,
        task_id: str,
        product: ProductInput,
        rules: list[Rule],
        optimized_fields: dict[WritableCopyField, str | list[str]],
    ) -> object:
        candidate = product.model_copy(update=optimized_fields)
        semantic_skill = self._semantic_inspection_skill or _UnavailableVerificationSemanticSkill()
        workflow = FoodInspectionWorkflow(
            rule_loader=lambda: list(rules),
            food_quality_skill=self._food_quality_skill,
            semantic_inspection_skill=semantic_skill,
        )
        return workflow.invoke(task_id=task_id, product=candidate)

    @staticmethod
    def _verification_failure_reasons(
        source_issues: list[Issue],
        requested_fields: list[WritableCopyField],
        verification_report: object,
    ) -> list[str]:
        from contracts.models import InspectionReport, RiskLevel

        if not isinstance(verification_report, InspectionReport):
            raise TypeError("optimization verification must return an InspectionReport")
        reasons: list[str] = []
        if verification_report.review_required:
            reasons.append("review_required")
        if verification_report.degradation_flags:
            reasons.append("degradation")
        source_rule_ids = {rule_id for issue in source_issues for rule_id in issue.rule_ids}
        for issue in verification_report.issues:
            if issue.risk_level is RiskLevel.HIGH:
                reasons.append("high_risk_issue")
            if issue.risk_level is RiskLevel.HIGH and not set(issue.rule_ids) & source_rule_ids:
                reasons.append("new_high_risk_issue")
            if issue.field in requested_fields and set(issue.rule_ids) & source_rule_ids:
                reasons.append("retained_source_issue")
        return list(dict.fromkeys(reasons))

    @staticmethod
    def _rule_ids(issues: list[Issue]) -> list[str]:
        return sorted({rule_id for issue in issues for rule_id in issue.rule_ids})

    def _result(
        self,
        task_id: str,
        request: OptimizationRequest,
        source_issues: list[Issue],
        artifact: CopyOptimizationArtifact,
        *,
        status: OptimizationStatus,
        verification_report: object | None = None,
        failure_reason: str | None = None,
    ) -> OptimizationResult:
        from contracts.models import InspectionReport

        if verification_report is not None and not isinstance(
            verification_report, InspectionReport
        ):
            raise TypeError("optimization verification must return an InspectionReport")
        return OptimizationResult(
            optimization_id=str(uuid4()),
            source_task_id=task_id,
            status=status,
            requested_fields=request.fields,
            optimized_fields=artifact.optimized_fields,
            referenced_issues=[
                OptimizationIssueReference(
                    field=issue.field,
                    evidence_span=issue.evidence_span,
                    rule_ids=issue.rule_ids,
                )
                for issue in source_issues
            ],
            referenced_rule_ids=artifact.referenced_rule_ids,
            verification_report=verification_report,
            failure_reason=failure_reason or artifact.failure_reason,
        )

    def _persist(self, result: OptimizationResult, traces: list[TraceEvent]) -> OptimizationResult:
        with self._session_factory() as session:
            InspectionRepository(session).add_traces(traces)
            OptimizationRepository(session).create_attempt(result)
            session.commit()
        return result

    @staticmethod
    def _optimization_trace(
        task_id: str, artifact: CopyOptimizationArtifact, *, attempt: int
    ) -> TraceEvent:
        return TraceEvent(
            task_id=task_id,
            step_name="copy_optimization",
            tool_or_skill_name="copy_optimization_skill",
            rule_ids=artifact.referenced_rule_ids,
            decision="生成优化候选文案" if artifact.failure_reason is None else "优化文案生成失败",
            status="success" if artifact.failure_reason is None else "failed",
            latency_ms=int(artifact.safe_metadata.get("latency_ms", 0)),
            metadata={
                **artifact.safe_metadata,
                "operation": "copy_optimization",
                "attempt": attempt,
            },
        )

    @staticmethod
    def _verification_trace(
        task_id: str,
        report: object,
        failure_reasons: list[str],
        *,
        attempt: int,
    ) -> TraceEvent:
        from contracts.models import InspectionReport

        if not isinstance(report, InspectionReport):
            raise TypeError("optimization verification must return an InspectionReport")
        return TraceEvent(
            task_id=task_id,
            step_name="optimization_verification",
            tool_or_skill_name="food_inspection_workflow",
            rule_ids=sorted({rule_id for issue in report.issues for rule_id in issue.rule_ids}),
            decision="二次质检通过" if not failure_reasons else "二次质检未通过",
            status="success" if not failure_reasons else "failed",
            latency_ms=0,
            metadata={
                "operation": "optimization_verification",
                "attempt": attempt,
                **({"error_category": "verification_failed"} if failure_reasons else {}),
            },
        )

    @staticmethod
    def _failure_reason(reasons: list[str]) -> str:
        return ",".join(reasons)
