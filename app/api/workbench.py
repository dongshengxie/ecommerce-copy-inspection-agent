from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy.orm import Session, sessionmaker

from agent.state.inspection import SemanticInspectionSkill
from app.api.inspections import InspectionCreatedResponse
from app.services.inspection import InspectionApplicationService
from contracts.workbench import WorkbenchInspectionSubmission, to_product_input


def create_workbench_router(
    session_factory: sessionmaker[Session],
    *,
    semantic_inspection_skill: SemanticInspectionSkill | None = None,
) -> APIRouter:
    """Expose the workbench boundary without accepting client-controlled product identity."""

    router = APIRouter(prefix="/api/v2/workbench", tags=["workbench"])
    service = InspectionApplicationService(
        session_factory, semantic_inspection_skill=semantic_inspection_skill
    )

    @router.post(
        "/inspections",
        response_model=InspectionCreatedResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_workbench_inspection(
        submission: WorkbenchInspectionSubmission,
        semantic_inspection: Literal["enabled", "disabled"] = Header(
            default="disabled", alias="X-Semantic-Inspection"
        ),
    ) -> InspectionCreatedResponse:
        try:
            report = service.create_inspection(
                to_product_input(submission),
                semantic_enabled=semantic_inspection == "enabled",
            )
        except Exception as error:
            raise HTTPException(status_code=500, detail="质检执行失败") from error
        return InspectionCreatedResponse(
            task_id=report.task_id,
            status=report.status.value,
            result_url=f"/api/v2/inspections/{report.task_id}/result",
        )

    return router
