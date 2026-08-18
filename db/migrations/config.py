from __future__ import annotations

import os

from app.config import Settings


def database_url_from_environment(configured_url: str | None = None) -> str:
    """Resolve explicit environment/config URLs before the MySQL Settings fallback."""
    explicit_url = os.environ.get("DATABASE_URL")
    if explicit_url:
        return explicit_url
    if configured_url and not configured_url.startswith("driver://"):
        return configured_url
    return Settings.from_environment().database_url()
