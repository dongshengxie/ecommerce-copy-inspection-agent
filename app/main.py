from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from agent.state.inspection import SemanticInspectionSkill
from app.api.inspections import create_inspection_router
from app.api.workbench import create_workbench_router
from app.config import Settings
from app.services.inspection import create_copy_optimization_skill, create_semantic_inspection_skill
from db.session import create_engine_and_session
from llm.copy_optimization import CopyOptimizationSkill


def create_app(
    session_factory: sessionmaker[Session] | None = None,
    *,
    semantic_inspection_skill: SemanticInspectionSkill | None = None,
    copy_optimization_skill: CopyOptimizationSkill | None = None,
) -> FastAPI:
    """Create the Phase 2 synchronous inspection API application."""
    settings = Settings.from_environment()
    app = FastAPI(title="电商商品文案质检与优化 Agent", version="0.1.0")
    resolved_session_factory = session_factory or create_engine_and_session(settings)
    resolved_semantic_inspection_skill = (
        semantic_inspection_skill
        if semantic_inspection_skill is not None
        else (None if session_factory is not None else create_semantic_inspection_skill(settings))
    )
    app.include_router(
        create_inspection_router(
            resolved_session_factory,
            semantic_inspection_skill=resolved_semantic_inspection_skill,
            copy_optimization_skill=(
                copy_optimization_skill
                if copy_optimization_skill is not None
                else None
                if session_factory is not None
                else create_copy_optimization_skill(settings)
            ),
        )
    )
    app.include_router(
        create_workbench_router(
            resolved_session_factory,
            semantic_inspection_skill=resolved_semantic_inspection_skill,
        )
    )
    return app


app = create_app()
