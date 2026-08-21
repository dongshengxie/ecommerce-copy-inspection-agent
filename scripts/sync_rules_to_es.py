from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import httpx
from elasticsearch import Elasticsearch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings  # noqa: E402  # Supports direct execution from the project root.
from contracts.models import Rule  # noqa: E402
from db.repositories.rules import RuleRepository  # noqa: E402
from db.session import create_engine_and_session  # noqa: E402
from rag.indexing import RuleIndexManager  # noqa: E402
from rag.providers import SiliconFlowEmbeddingProvider  # noqa: E402


class RuleIndexSynchronizer(Protocol):
    """The index operations required by the one-way synchronization command."""

    def ensure_index(self) -> None:
        """Create the derived index if absent."""

    def sync_rules(self, rules: list[Rule]) -> int:
        """Upsert the supplied source-of-truth rules into the derived index."""


class RuleIndexRebuilder(Protocol):
    def rebuild_rules(self, rules: list[Rule]) -> int:
        """Replace the derived index with the supplied active rule baseline."""


def sync_enabled_food_rules(
    rule_loader: Callable[[], list[Rule]], index_manager: RuleIndexSynchronizer
) -> int:
    """Read current rules once, then create and idempotently update the derived ES index."""
    rules = rule_loader()
    index_manager.ensure_index()
    return index_manager.sync_rules(rules)


def rebuild_enabled_food_rules(
    rule_loader: Callable[[], list[Rule]], index_manager: RuleIndexRebuilder
) -> int:
    """Rebuild the derived ES index from the MySQL active-rule read boundary."""
    return index_manager.rebuild_rules(rule_loader())


def main() -> None:
    settings = Settings.from_environment()
    if not settings.bge_api_base_url or not settings.bge_api_key:
        raise SystemExit("请先配置 BGE_API_BASE_URL 和 BGE_API_KEY，再同步规则索引。")

    session_factory = create_engine_and_session(settings)
    with session_factory() as session, httpx.Client() as http_client:
        index_manager = RuleIndexManager(
            client=Elasticsearch(settings.elasticsearch_url),
            embedding_provider=SiliconFlowEmbeddingProvider(
                client=http_client,
                base_url=settings.bge_api_base_url,
                api_key=settings.bge_api_key,
                model=settings.bge_embedding_model,
            ),
            index_name=f"{settings.elasticsearch_index_prefix}_v1",
        )
        synced_count = rebuild_enabled_food_rules(
            RuleRepository(session).list_enabled_food_rules, index_manager
        )
    print(f"已同步 {synced_count} 条已启用食品规则到 Elasticsearch。")


if __name__ == "__main__":
    main()
