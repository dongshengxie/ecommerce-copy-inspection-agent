from __future__ import annotations

import json
from pathlib import Path

from elasticsearch import Elasticsearch

from contracts.models import Rule
from rag.indexing import RuleIndexManager

ROOT = Path(__file__).resolve().parents[2]
INDEX_NAME = "food_rules_phase4_test"


class _FixedEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        assert text
        return [0.125] * 1024


def _rules() -> list[Rule]:
    with (ROOT / "data/rules/food_rules.json").open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


def test_real_elasticsearch_index_is_idempotent() -> None:
    client = Elasticsearch("http://127.0.0.1:9200")
    client.indices.delete(index=INDEX_NAME, ignore_unavailable=True)
    manager = RuleIndexManager(
        client=client,
        embedding_provider=_FixedEmbeddingProvider(),
        index_name=INDEX_NAME,
    )

    try:
        manager.ensure_index()
        manager.sync_rules(_rules())
        manager.sync_rules(_rules())

        mapping = client.indices.get_mapping(index=INDEX_NAME)[INDEX_NAME]["mappings"]
        assert mapping["properties"]["retrieval_vector"]["dims"] == 1024
        assert client.count(index=INDEX_NAME)["count"] == 25
    finally:
        client.indices.delete(index=INDEX_NAME, ignore_unavailable=True)
