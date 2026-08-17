from __future__ import annotations

from typing import Protocol

from contracts.models import Rule
from rag.models import EmbeddingProvider, RuleIndexDocument


class ElasticsearchIndexClient(Protocol):
    """The minimal Elasticsearch boundary required by rule-index operations."""

    indices: object

    def bulk(self, *, operations: list[dict[str, object]], refresh: str) -> object:
        """Upsert ordered index operations."""


class RuleIndexManager:
    """Create and rebuild the derived Elasticsearch rule index."""

    def __init__(
        self,
        *,
        client: ElasticsearchIndexClient,
        embedding_provider: EmbeddingProvider,
        index_name: str,
    ) -> None:
        self._client = client
        self._embedding_provider = embedding_provider
        self._index_name = index_name

    def ensure_index(self) -> None:
        """Create the versioned rule index once with the approved mapping."""
        indices = self._client.indices
        if not hasattr(indices, "exists") or not hasattr(indices, "create"):
            raise TypeError("Elasticsearch client must expose indices.exists and indices.create")
        if not indices.exists(index=self._index_name):  # type: ignore[union-attr]
            indices.create(index=self._index_name, mappings=self._mapping())  # type: ignore[union-attr]

    def sync_rules(self, rules: list[Rule]) -> int:
        """Idempotently upsert one Elasticsearch document per supplied Rule version."""
        operations: list[dict[str, object]] = []
        for rule in sorted(rules, key=lambda item: (item.rule_id, item.version)):
            vector = self._embedding_provider.embed(self._retrieval_text(rule))
            document = RuleIndexDocument.from_rule(rule, vector)
            operations.extend(
                [
                    {"index": {"_index": self._index_name, "_id": document.document_id}},
                    document.model_dump(mode="json"),
                ]
            )

        if operations:
            self._client.bulk(operations=operations, refresh="wait_for")
        return len(operations) // 2

    @staticmethod
    def _retrieval_text(rule: Rule) -> str:
        """Use the same rule-only source text for embedding and document storage."""
        return RuleIndexDocument.from_rule(rule, [0.0] * 1024).retrieval_text

    @staticmethod
    def _mapping() -> dict[str, object]:
        return {
            "properties": {
                "rule_id": {"type": "keyword"},
                "version": {"type": "keyword"},
                "category": {"type": "keyword"},
                "status": {"type": "keyword"},
                "effective_at": {"type": "date"},
                "field_scope": {"type": "keyword"},
                "issue_type": {"type": "keyword"},
                "risk_level": {"type": "keyword"},
                "rule_strength": {"type": "keyword"},
                "retrieval_text": {"type": "text"},
                "retrieval_vector": {
                    "type": "dense_vector",
                    "dims": 1024,
                    "index": True,
                    "similarity": "cosine",
                },
            }
        }
