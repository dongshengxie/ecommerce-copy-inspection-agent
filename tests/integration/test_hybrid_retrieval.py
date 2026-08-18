from __future__ import annotations

import json
from pathlib import Path

from elasticsearch import Elasticsearch

from contracts.models import FoodAttributes, ProductInput, Rule
from rag.indexing import RuleIndexManager
from rag.retriever import RuleRetriever

ROOT = Path(__file__).resolve().parents[2]
INDEX_NAME = "food_rules_hybrid_retrieval_test"


class _FixedEmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        assert text
        return [0.125] * 1024


class _FixedRerankerProvider:
    def rerank(self, query: str, documents: list[str]) -> list[float]:
        assert query
        return [float(len(documents) - index) for index in range(len(documents))]


def _rules() -> list[Rule]:
    with (ROOT / "data/rules/food_rules.json").open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


def _product() -> ProductInput:
    return ProductInput(
        product_id="product-1",
        product_revision=1,
        category="食品",
        title="产品可能治疗疾病",
        selling_points=[],
        description="产品可能治疗疾病",
        attributes=FoodAttributes(
            ingredients="茶叶",
            shelf_life="18个月",
            storage_method="阴凉干燥处保存",
            origin="福建",
        ),
        marketing_description="",
        trigger_source="manual",
    )


def test_real_elasticsearch_hybrid_retrieval_returns_only_current_food_rules() -> None:
    client = Elasticsearch("http://127.0.0.1:9200")
    client.indices.delete(index=INDEX_NAME, ignore_unavailable=True)
    rules = _rules()
    index_manager = RuleIndexManager(
        client=client,
        embedding_provider=_FixedEmbeddingProvider(),
        index_name=INDEX_NAME,
    )
    retriever = RuleRetriever(
        client=client,
        embedding_provider=_FixedEmbeddingProvider(),
        reranker_provider=_FixedRerankerProvider(),
        index_name=INDEX_NAME,
    )

    try:
        index_manager.ensure_index()
        index_manager.sync_rules(rules)
        result = retriever.retrieve(_product(), rules)

        assert 1 <= len(result.candidates) <= 5
        assert set(result.candidate_rule_ids).issubset({rule.rule_id for rule in rules})
        assert result.trace_metadata["strategy"] == "bm25+knn_rrf+rerank"
    finally:
        client.indices.delete(index=INDEX_NAME, ignore_unavailable=True)
