from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from agent.state.inspection import SemanticInspectionSkill
from app.services.inspection import InspectionApplicationService
from app.services.optimization import (
    OptimizationApplicationService,
    OptimizationConflictError,
    OptimizationNotFoundError,
)
from contracts.models import ProductInput
from contracts.optimization import OptimizationRequest, OptimizationResult
from db.repositories.inspections import InspectionRepository
from db.repositories.rules import RuleRepository
from llm.copy_optimization import CopyOptimizationSkill


class InspectionCreatedResponse(BaseModel):
    task_id: str
    status: str
    result_url: str


class InspectionTaskResponse(BaseModel):
    task_id: str
    status: str
    trigger_source: str
    rule_version: str


class TraceEventResponse(BaseModel):
    step_name: str
    tool_or_skill_name: str
    rule_ids: list[str]
    decision: str
    status: Literal["success", "failed"]
    latency_ms: int
    metadata: dict[str, object]


class InspectionTraceResponse(BaseModel):
    task_id: str
    events: list[TraceEventResponse]


class RuleEvidenceItemResponse(BaseModel):
    rule_id: str
    version: str
    field_scope: list[str]
    risk_level: str
    rule_text: str
    rewrite_hint: str


class RuleEvidenceResponse(BaseModel):
    task_id: str
    rules: list[RuleEvidenceItemResponse]


def create_inspection_router(
    session_factory: sessionmaker[Session],
    *,
    semantic_inspection_skill: SemanticInspectionSkill | None = None,
    copy_optimization_skill: CopyOptimizationSkill | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v2/inspections", tags=["inspections"])
    service = InspectionApplicationService(
        session_factory, semantic_inspection_skill=semantic_inspection_skill
    )
    optimization_service = OptimizationApplicationService(
        session_factory,
        copy_optimization_skill=copy_optimization_skill,
        semantic_inspection_skill=semantic_inspection_skill,
    )

    @router.post("", response_model=InspectionCreatedResponse, status_code=status.HTTP_201_CREATED)
    def create_inspection(
        product: ProductInput,
        semantic_inspection: Literal["enabled", "disabled"] = Header(
            default="disabled", alias="X-Semantic-Inspection"
        ),
    ) -> InspectionCreatedResponse:
        try:
            report = service.create_inspection(
                product,
                semantic_enabled=semantic_inspection == "enabled",
            )
        except Exception as error:
            raise HTTPException(status_code=500, detail="质检执行失败") from error
        return InspectionCreatedResponse(
            task_id=report.task_id,
            status=report.status.value,
            result_url=f"/api/v2/inspections/{report.task_id}/result",
        )

    @router.get("/{task_id}", response_model=InspectionTaskResponse)
    def get_inspection(task_id: str) -> InspectionTaskResponse:
        with session_factory() as session:
            task = InspectionRepository(session).get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="质检任务不存在")
        return InspectionTaskResponse(
            task_id=task.id,
            status=task.status,
            trigger_source=task.trigger_source,
            rule_version=task.rule_version,
        )

    @router.get("/{task_id}/result")
    def get_inspection_result(task_id: str) -> dict[str, object]:
        with session_factory() as session:
            report = InspectionRepository(session).get_report(task_id)
        if report is None:
            raise HTTPException(status_code=404, detail="质检结果不存在")
        return report.model_dump(mode="json")

    @router.get("/{task_id}/trace", response_model=InspectionTraceResponse)
    def get_inspection_trace(task_id: str) -> InspectionTraceResponse:
        with session_factory() as session:
            repository = InspectionRepository(session)
            if repository.get_task(task_id) is None:
                raise HTTPException(status_code=404, detail="质检任务不存在")
            events = repository.list_trace_summaries(task_id)
        return InspectionTraceResponse(task_id=task_id, events=events)

    @router.get("/{task_id}/rule-evidence", response_model=RuleEvidenceResponse)
    def get_rule_evidence(task_id: str) -> RuleEvidenceResponse:
        with session_factory() as session:
            inspection_repository = InspectionRepository(session)
            report = inspection_repository.get_report(task_id)
            if report is None:
                raise HTTPException(status_code=404, detail="质检结果不存在")
            rule_ids = {rule_id for issue in report.issues for rule_id in issue.rule_ids}
            rules = RuleRepository(session).list_by_task_rule_references(task_id, rule_ids)
        return RuleEvidenceResponse(
            task_id=task_id,
            rules=[
                RuleEvidenceItemResponse(
                    rule_id=rule.rule_id,
                    version=rule.version,
                    field_scope=rule.field_scope,
                    risk_level=rule.risk_level.value,
                    rule_text=rule.rule_text,
                    rewrite_hint=rule.rewrite_hint,
                )
                for rule in rules
            ],
        )

    @router.post("/{task_id}/optimization", response_model=OptimizationResult)
    def optimize_inspection(task_id: str, request: OptimizationRequest) -> OptimizationResult:
        try:
            return optimization_service.optimize(task_id, request)
        except OptimizationNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except OptimizationConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return router
