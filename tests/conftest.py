from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def _alembic_config(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def migrated_test_database() -> str:
    """Provide an empty, migrated database reserved for one MySQL test."""
    settings = Settings.from_environment()
    database_url = settings.database_url(settings.mysql_test_database)
    config = _alembic_config(database_url)
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    yield database_url

    command.downgrade(config, "base")


@pytest.fixture
def db_session(migrated_test_database: str) -> Session:
    engine = create_engine(migrated_test_database)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
