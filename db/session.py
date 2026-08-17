from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings


def create_engine_and_session(
    settings: Settings, database_name: str | None = None
) -> sessionmaker[Session]:
    engine = create_engine(settings.database_url(database_name), pool_pre_ping=True)
    return sessionmaker(bind=engine, expire_on_commit=False)
