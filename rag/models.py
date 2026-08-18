from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field

from contracts.models import Rule


class EmbeddingProvider(Protocol):
    """Produce one BGE-compatible dense vector for a retrieval document."""

    def embed(self, text: str) -> list[float]:
        """Return a 1024-dimensional vector for non-empty text."""


class RerankerProvider(Protocol):
    """Score candidate documents against one retrieval query."""

    def rerank(self, query: str, documents: list[str]) -> list[float]:
        """Return one finite score for every input document in its original order."""


@dataclass(frozen=True)
class RetrievalCandidate:
    """A current Rule selected from the derived Elasticsearch index."""

    rule: Rule
    rrf_score: float
    reranker_score: float


@dataclass(frozen=True)
class RetrievalResult:
    """RAG candidates plus safe observability metadata for one retrieval."""

    candidates: list[RetrievalCandidate]
    trace_metadata: dict[str, object]

    @property
    def candidate_rule_ids(self) -> list[str]:
        return [candidate.rule.rule_id for candidate in self.candidates]


class RuleIndexDocument(BaseModel):
    """The rebuildable Elasticsearch projection of one versioned Rule."""

    document_id: str
    rule_id: str
    version: str
    category: str
    status: str
    effective_at: str
    field_scope: list[str]
    issue_type: str
    risk_level: str
    rule_strength: str
    retrieval_text: str
    retrieval_vector: list[float] = Field(min_length=1024, max_length=1024)

    @classmethod
    def from_rule(cls, rule: Rule, retrieval_vector: list[float]) -> RuleIndexDocument:
        """Build a rule-only, versioned search document from the frozen Contract."""
        if len(retrieval_vector) != 1024:
            raise ValueError("规则检索向量必须为 1024 维")

        retrieval_text = "\n".join(
            [
                f"规则 ID: {rule.rule_id}",
                f"规则版本: {rule.version}",
                f"适用字段: {'、'.join(rule.field_scope)}",
                f"问题类型: {rule.issue_type}",
                f"规则正文: {rule.rule_text}",
                f"风险示例: {'；'.join(rule.bad_examples)}",
                f"改写提示: {rule.rewrite_hint}",
            ]
        )
        return cls(
            document_id=f"{rule.rule_id}:{rule.version}",
            rule_id=rule.rule_id,
            version=rule.version,
            category=rule.category,
            status=rule.status,
            effective_at=rule.effective_at,
            field_scope=rule.field_scope,
            issue_type=rule.issue_type,
            risk_level=rule.risk_level.value,
            rule_strength=rule.rule_strength,
            retrieval_text=retrieval_text,
            retrieval_vector=retrieval_vector,
        )
