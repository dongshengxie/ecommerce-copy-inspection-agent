from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter
from typing import Protocol

from elasticsearch import ApiError, ConnectionError, TransportError

from contracts.models import ProductInput, Rule
from rag.models import (
    EmbeddingProvider,
    RerankerProvider,
    RetrievalCandidate,
    RetrievalResult,
)
from rag.providers import RagUnavailableError

_RETRIEVAL_SIZE = 10
_RRF_K = 60
_RESULT_SIZE = 5


class ElasticsearchSearchClient(Protocol):
    """The small Elasticsearch search boundary used by food-rule retrieval."""

    def search(self, **kwargs: object) -> object:
        """Run one bounded query against the derived rule index."""


class RuleRetriever:
    """Retrieve current food Rule candidates through BM25, kNN, RRF, and reranking."""

    def __init__(
        self,
        *,
        client: ElasticsearchSearchClient,
        embedding_provider: EmbeddingProvider,
        reranker_provider: RerankerProvider,
        index_name: str,
    ) -> None:
        self._client = client
        self._embedding_provider = embedding_provider
        self._reranker_provider = reranker_provider
        self._index_name = index_name

    def retrieve(self, product: ProductInput, rules: list[Rule]) -> RetrievalResult:
        """Return at most five current enabled food rules as semantic evidence candidates."""
        started_at = perf_counter()
        query = self._build_query(product)
        filters = self._filters()
        query_vector = self._embedding_provider.embed(query)

        try:
            bm25_hits = self._hits(
                self._client.search(
                    index=self._index_name,
                    size=_RETRIEVAL_SIZE,
                    query={
                        "bool": {
                            "filter": filters,
                            "must": [{"match": {"retrieval_text": {"query": query}}}],
                        }
                    },
                )
            )
            vector_hits = self._hits(
                self._client.search(
                    index=self._index_name,
                    size=_RETRIEVAL_SIZE,
                    knn={
                        "field": "retrieval_vector",
                        "query_vector": query_vector,
                        "k": _RETRIEVAL_SIZE,
                        "num_candidates": 100,
                        "filter": filters,
                    },
                )
            )
        except (ApiError, ConnectionError, OSError, TransportError, TypeError, ValueError) as error:
            raise RagUnavailableError("elasticsearch_search_failed") from error

        fused = self._fuse_hits(bm25_hits, vector_hits)
        if not fused:
            return self._result([], started_at)

        ranked_hits = sorted(
            fused.values(), key=lambda item: (-item["rrf_score"], item["key"])
        )[:_RETRIEVAL_SIZE]
        reranker_scores = self._reranker_provider.rerank(
            query, [item["retrieval_text"] for item in ranked_hits]
        )
        if len(reranker_scores) != len(ranked_hits):
            raise RagUnavailableError("reranker_score_count_mismatch")

        current_rules = {
            (rule.rule_id, rule.version): rule
            for rule in rules
            if rule.category == "食品" and rule.status == "enabled"
        }
        candidates: list[RetrievalCandidate] = []
        for hit, reranker_score in zip(ranked_hits, reranker_scores, strict=True):
            rule = current_rules.get(hit["key"])
            if rule is not None:
                candidates.append(
                    RetrievalCandidate(
                        rule=rule,
                        rrf_score=hit["rrf_score"],
                        reranker_score=reranker_score,
                    )
                )

        candidates.sort(
            key=lambda item: (
                -item.reranker_score,
                -item.rrf_score,
                item.rule.rule_id,
                item.rule.version,
            )
        )
        return self._result(candidates[:_RESULT_SIZE], started_at)

    @staticmethod
    def _build_query(product: ProductInput) -> str:
        values = [
            product.title,
            *product.selling_points,
            product.description,
            product.marketing_description,
            *(
                value
                for value in product.attributes.model_dump(exclude_none=True).values()
                if isinstance(value, str)
            ),
        ]
        query = "\n".join(value.strip() for value in values if value.strip())
        if not query:
            raise RagUnavailableError("retrieval_query_empty")
        return query

    @staticmethod
    def _filters() -> list[dict[str, dict[str, str]]]:
        return [
            {"term": {"category": "食品"}},
            {"term": {"status": "enabled"}},
        ]

    @staticmethod
    def _hits(response: object) -> list[Mapping[str, object]]:
        body = getattr(response, "body", response)
        if not isinstance(body, Mapping):
            raise ValueError("Elasticsearch response body must be a mapping")
        hits = body.get("hits")
        if not isinstance(hits, Mapping):
            raise ValueError("Elasticsearch response misses hits")
        documents = hits.get("hits")
        if not isinstance(documents, list):
            raise ValueError("Elasticsearch response misses document hits")
        return [document for document in documents if isinstance(document, Mapping)]

    @staticmethod
    def _fuse_hits(
        bm25_hits: list[Mapping[str, object]], vector_hits: list[Mapping[str, object]]
    ) -> dict[tuple[str, str], dict[str, object]]:
        fused: dict[tuple[str, str], dict[str, object]] = {}
        for hits in (bm25_hits, vector_hits):
            for rank, hit in enumerate(hits, start=1):
                source = hit.get("_source")
                if not isinstance(source, Mapping):
                    continue
                rule_id = source.get("rule_id")
                version = source.get("version")
                retrieval_text = source.get("retrieval_text")
                if not all(
                    isinstance(value, str) and value
                    for value in (rule_id, version, retrieval_text)
                ):
                    continue
                key = (rule_id, version)
                candidate = fused.setdefault(
                    key,
                    {"key": key, "retrieval_text": retrieval_text, "rrf_score": 0.0},
                )
                candidate["rrf_score"] = float(candidate["rrf_score"]) + 1 / (_RRF_K + rank)
        return fused

    def _result(
        self, candidates: list[RetrievalCandidate], started_at: float
    ) -> RetrievalResult:
        return RetrievalResult(
            candidates=candidates,
            trace_metadata={
                "strategy": "bm25+knn_rrf+rerank",
                "candidate_rule_ids": [candidate.rule.rule_id for candidate in candidates],
                "index_name": self._index_name,
                "latency_ms": int((perf_counter() - started_at) * 1000),
            },
        )
