from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from contracts.models import Issue, ProductInput
from llm.models import SemanticFinding, SemanticSkillResult
from llm.providers import LLMProvider, LLMUnavailableError
from rag.models import RetrievalCandidate

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "semantic_risk" / "1.0.0.json"


class _SemanticPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[SemanticFinding] = Field(default_factory=list)


class SemanticRiskSkill:
    """Validate one structured semantic pass against a bounded RAG candidate set."""

    def __init__(self, *, llm_provider: LLMProvider, prompt_version: str) -> None:
        self._llm_provider = llm_provider
        self._prompt_version = prompt_version

    def inspect(
        self,
        product: ProductInput,
        candidates: list[RetrievalCandidate],
        deterministic_issues: list[Issue],
    ) -> SemanticSkillResult:
        """Return validated semantic issues, or a review-required degradation result."""
        del deterministic_issues
        messages = self._messages(product, candidates)
        try:
            response = self._llm_provider.complete_structured(messages)
        except LLMUnavailableError:
            return SemanticSkillResult(
                degradation_flags=["llm_failed"],
                review_required=True,
                trace_metadata={"prompt_version": self._prompt_version},
            )

        for attempt in range(2):
            try:
                findings = _SemanticPayload.model_validate(response.payload).findings
                return SemanticSkillResult(
                    issues=self._issues(product, candidates, findings),
                    trace_metadata=self._trace_metadata(response),
                )
            except (ValidationError, ValueError):
                if attempt == 1:
                    break
                try:
                    response = self._llm_provider.complete_structured(
                        messages
                        + [
                            {
                                "role": "user",
                                "content": "上一次输出不符合 JSON schema，请仅返回合规 JSON。",
                            }
                        ]
                    )
                except LLMUnavailableError:
                    return SemanticSkillResult(
                        degradation_flags=["llm_failed"],
                        review_required=True,
                        trace_metadata={"prompt_version": self._prompt_version},
                    )
        return SemanticSkillResult(
            degradation_flags=["structured_output_invalid"],
            review_required=True,
            trace_metadata=self._trace_metadata(response),
        )

    def _messages(
        self, product: ProductInput, candidates: list[RetrievalCandidate]
    ) -> list[dict[str, str]]:
        prompt = json.loads(_PROMPT_PATH.read_text(encoding="utf-8"))
        return [
            {"role": "system", "content": str(prompt["system"])},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "product": product.model_dump(mode="json"),
                        "candidate_rules": [
                            {
                                "rule_id": candidate.rule.rule_id,
                                "version": candidate.rule.version,
                                "field_scope": candidate.rule.field_scope,
                                "risk_level": candidate.rule.risk_level.value,
                                "rule_text": candidate.rule.rule_text,
                                "rewrite_hint": candidate.rule.rewrite_hint,
                            }
                            for candidate in candidates
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ]

    def _issues(
        self,
        product: ProductInput,
        candidates: list[RetrievalCandidate],
        findings: list[SemanticFinding],
    ) -> list[Issue]:
        candidate_rules = {
            (candidate.rule.rule_id, candidate.rule.version): candidate.rule
            for candidate in candidates
        }
        issues: list[Issue] = []
        for finding in findings:
            rule = candidate_rules.get((finding.rule_id, finding.rule_version))
            if rule is None:
                raise ValueError("semantic finding references a non-candidate rule")
            evidence = self._field_value(product, finding.field)
            if (
                not self._field_allowed(rule.field_scope, finding.field)
                or finding.evidence_span not in evidence
            ):
                raise ValueError("semantic finding evidence is not grounded in the source field")
            issues.append(
                Issue(
                    field=finding.field,
                    issue_type=rule.issue_type,
                    risk_level=rule.risk_level,
                    evidence_span=finding.evidence_span,
                    evidence=finding.rationale,
                    rule_ids=[rule.rule_id],
                    source=["semantic_risk_skill"],
                    confidence=finding.confidence,
                    suggestion=finding.suggestion,
                )
            )
        return issues

    @staticmethod
    def _field_allowed(field_scope: list[str], field: str) -> bool:
        return field in field_scope or (
            "attributes" in field_scope and field.startswith("attributes.")
        )

    @staticmethod
    def _field_value(product: ProductInput, field: str) -> str:
        text_fields = {
            "title": product.title,
            "selling_points": "\n".join(product.selling_points),
            "description": product.description,
            "marketing_description": product.marketing_description,
        }
        if field in text_fields:
            return text_fields[field]
        if field.startswith("attributes."):
            attribute_name = field.removeprefix("attributes.")
            value = getattr(product.attributes, attribute_name, None)
            if isinstance(value, str):
                return value
        raise ValueError("semantic finding references an unsupported product field")

    def _trace_metadata(self, response: object) -> dict[str, object]:
        from llm.models import LLMResponse

        if not isinstance(response, LLMResponse):
            raise TypeError("LLM provider must return LLMResponse")
        return {
            "prompt_version": self._prompt_version,
            "model_name": response.model_name,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "latency_ms": response.latency_ms,
        }
