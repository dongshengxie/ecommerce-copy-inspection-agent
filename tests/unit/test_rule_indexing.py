from __future__ import annotations

import json
from pathlib import Path

from contracts.models import Rule
from rag.indexing import RuleIndexManager
from rag.models import RuleIndexDocument

ROOT = Path(__file__).resolve().parents[2]


class _FakeIndices:
    def __init__(self) -> None:
        self.created: dict[str, dict[str, object]] = {}

    def exists(self, *, index: str) -> bool:
        return index in self.created

    def create(self, *, index: str, mappings: dict[str, object]) -> None:
        self.created[index] = mappings


class _FakeElasticsearch:
    def __init__(self) -> None:
        self.indices = _FakeIndices()
        self.documents: dict[tuple[str, str], dict[str, object]] = {}

    def bulk(self, *, operations: list[dict[str, object]], refresh: str) -> None:
        assert refresh == "wait_for"
        for action, document in zip(operations[::2], operations[1::2], strict=True):
            index_action = action["index"]
            assert isinstance(index_action, dict)
            index_name = index_action["_index"]
            document_id = index_action["_id"]
            assert isinstance(index_name, str)
            assert isinstance(document_id, str)
            self.documents[(index_name, document_id)] = document


class _FixedEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        assert text
        return [0.125] * 1024


def _rules() -> list[Rule]:
    with (ROOT / "data/rules/food_rules.json").open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


def test_rule_document_projects_only_versioned_rule_content() -> None:
    rule = _rules()[0]

    document = RuleIndexDocument.from_rule(rule, [0.125] * 1024)

    assert document.document_id == "food_claim_001:1.1.0"
    assert document.category == "食品"
    assert document.status == "enabled"
    assert "普通食品文案不得明示或暗示疾病治疗效果。" in document.retrieval_text
    assert document.retrieval_vector == [0.125] * 1024
    assert "product" not in document.model_dump()


def test_sync_upserts_each_rule_once_and_creates_1024_vector_mapping() -> None:
    client = _FakeElasticsearch()
    manager = RuleIndexManager(
        client=client,
        embedding_provider=_FixedEmbeddingProvider(),
        index_name="food_rules_v1",
    )
    rules = _rules()

    manager.ensure_index()
    first_count = manager.sync_rules(rules)
    second_count = manager.sync_rules(rules)

    properties = client.indices.created["food_rules_v1"]["properties"]
    assert isinstance(properties, dict)
    assert properties["retrieval_vector"] == {
        "type": "dense_vector",
        "dims": 1024,
        "index": True,
        "similarity": "cosine",
    }
    assert first_count == 25
    assert second_count == 25
    assert len(client.documents) == 25
    indexed_rule = client.documents[("food_rules_v1", "food_claim_001:1.1.0")]
    assert indexed_rule["rule_id"] == "food_claim_001"
