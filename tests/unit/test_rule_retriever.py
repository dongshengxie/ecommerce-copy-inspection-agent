from __future__ import annotations

from contracts.models import FoodAttributes, ProductInput, Rule
from rag.retriever import RuleRetriever


def _product() -> ProductInput:
    return ProductInput(
        product_id="product-1",
        product_revision=1,
        category="食品",
        title="特级茉莉花茶",
        selling_points=["清香回甘"],
        description="每日饮用，清新口气。",
        attributes=FoodAttributes(
            ingredients="茉莉花茶",
            shelf_life="18个月",
            storage_method="阴凉干燥处保存",
            origin="福建",
        ),
        marketing_description="品质好茶",
        trigger_source="manual",
    )


def _rule(rule_id: str, version: str = "1.0.0") -> Rule:
    return Rule(
        rule_id=rule_id,
        version=version,
        category="食品",
        field_scope=["description"],
        issue_type="claim",
        risk_level="medium",
        rule_strength="must",
        rule_text=f"{rule_id} 的规则正文",
        bad_examples=[],
        rewrite_hint="调整措辞",
        status="enabled",
        effective_at="2026-01-01",
    )


class _FakeElasticsearch:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def search(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        if "knn" in kwargs:
            return {
                "hits": {
                    "hits": [
                        {
                            "_source": {
                                "rule_id": "rule-2",
                                "version": "1.0.0",
                                "retrieval_text": "规则二",
                            }
                        },
                        {
                            "_source": {
                                "rule_id": "stale-rule",
                                "version": "1.0.0",
                                "retrieval_text": "旧规则",
                            }
                        },
                    ]
                }
            }
        return {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "rule_id": "rule-1",
                            "version": "1.0.0",
                            "retrieval_text": "规则一",
                        }
                    },
                    {
                        "_source": {
                            "rule_id": "rule-2",
                            "version": "1.0.0",
                            "retrieval_text": "规则二",
                        }
                    },
                ]
            }
        }


class _EmbeddingProvider:
    def embed(self, text: str) -> list[float]:
        assert "特级茉莉花茶" in text
        assert "阴凉干燥处保存" in text
        return [0.5] * 1024


class _RerankerProvider:
    def rerank(self, query: str, documents: list[str]) -> list[float]:
        assert "每日饮用" in query
        assert documents == ["规则二", "规则一", "旧规则"]
        return [0.3, 0.9, 1.0]


def test_retriever_fuses_rankings_and_excludes_stale_rule_before_returning_candidates() -> None:
    client = _FakeElasticsearch()
    retriever = RuleRetriever(
        client=client,
        embedding_provider=_EmbeddingProvider(),
        reranker_provider=_RerankerProvider(),
        index_name="food_rules_v1",
    )

    result = retriever.retrieve(_product(), [_rule("rule-1"), _rule("rule-2")])

    assert result.candidate_rule_ids == ["rule-1", "rule-2"]
    assert result.trace_metadata["strategy"] == "bm25+knn_rrf+rerank"
    assert result.trace_metadata["index_name"] == "food_rules_v1"
    assert len(client.calls) == 2
    bm25_query = client.calls[0]["query"]
    assert isinstance(bm25_query, dict)
    assert bm25_query["bool"]["filter"] == [
        {"term": {"category": "食品"}},
        {"term": {"status": "enabled"}},
    ]
    assert "特级茉莉花茶" in bm25_query["bool"]["must"][0]["match"]["retrieval_text"]["query"]
    assert client.calls[1]["knn"] == {
        "field": "retrieval_vector",
        "query_vector": [0.5] * 1024,
        "k": 10,
        "num_candidates": 100,
        "filter": [
            {"term": {"category": "食品"}},
            {"term": {"status": "enabled"}},
        ],
    }
