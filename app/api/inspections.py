from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from app.services.inspection import InspectionApplicationService
from contracts.models import ProductInput
from db.repositories.inspections import InspectionRepository


class InspectionCreatedResponse(BaseModel):
    task_id: str
    status: str
    result_url: str


class InspectionTaskResponse(BaseModel):
    task_id: str
    status: str
    trigger_source: str
    rule_version: str


def create_inspection_router(session_factory: sessionmaker[Session]) -> APIRouter:
    router = APIRouter(prefix="/api/v2/inspections", tags=["inspections"])
    service = InspectionApplicationService(session_factory)

    @router.post("", response_model=InspectionCreatedResponse, status_code=status.HTTP_201_CREATED)
    def create_inspection(product: ProductInput) -> InspectionCreatedResponse:
        try:
            report = service.create_inspection(product)
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

    return router
