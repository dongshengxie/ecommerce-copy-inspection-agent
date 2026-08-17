from __future__ import annotations

from sqlalchemy import select

from contracts.models import ProductInput, TraceEvent
from db.models.core import AgentTraceModel
from db.repositories.inspections import InspectionRepository


def _product() -> ProductInput:
    return ProductInput.model_validate(
        {
            "product_id": "food-trace-001",
            "product_revision": 1,
            "category": "食品",
            "title": "茉莉花茶 30g",
            "selling_points": ["独立袋泡"],
            "description": "清香口感。",
            "attributes": {
                "ingredients": "绿茶、茉莉花",
                "shelf_life": "18个月",
                "storage_method": "阴凉干燥处保存",
                "origin": "浙江省杭州市",
            },
            "marketing_description": "30g 盒装。",
            "trigger_source": "test",
        }
    )


def test_failure_trace_persists_safe_metadata(db_session) -> None:
    repository = InspectionRepository(db_session)
    revision = repository.get_or_create_product_revision(_product())
    task = repository.create_running_task(revision.id, "test")
    repository.fail_task(
        task.id,
        RuntimeError("provider unavailable"),
        TraceEvent(
            task_id=task.id,
            step_name="semantic_risk_skill",
            tool_or_skill_name="deepseek_provider",
            rule_ids=["food_claim_001"],
            decision="回退到确定性质检",
            status="failed",
            latency_ms=12,
            error="provider unavailable",
            metadata={
                "prompt_version": "1.0.0",
                "model_name": "deepseek-chat",
                "degradation": "llm_failed",
            },
        ),
    )
    db_session.commit()

    assert db_session.scalar(select(AgentTraceModel.metadata_json)) == {
        "prompt_version": "1.0.0",
        "model_name": "deepseek-chat",
        "degradation": "llm_failed",
    }
