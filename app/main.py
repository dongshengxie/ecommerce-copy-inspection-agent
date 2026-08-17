from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy.orm import Session, sessionmaker

from app.api.inspections import create_inspection_router
from app.config import Settings
from db.session import create_engine_and_session


def create_app(session_factory: sessionmaker[Session] | None = None) -> FastAPI:
    """Create the Phase 2 synchronous inspection API application."""
    app = FastAPI(title="电商商品文案质检与优化 Agent", version="0.1.0")
    app.include_router(
        create_inspection_router(
            session_factory or create_engine_and_session(Settings.from_environment())
        )
    )
    return app


app = create_app()
