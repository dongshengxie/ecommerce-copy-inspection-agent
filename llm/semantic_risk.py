from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from contracts.models import Issue, ProductInput, Rule
from llm.models import SemanticFinding, SemanticSkillResult
from llm.providers import LLMProvider, LLMUnavailableError
from rag.models import RetrievalCandidate, RetrievalResult
from rag.providers import RagUnavailableError

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "semantic_risk" / "1.0.0.json"
_STRUCTURED_OUTPUT_CONTRACT = """
只返回一个 JSON object，不要 Markdown 或额外文本。严格使用以下结构：
{"findings":[
  {"rule_id":"候选规则 ID","rule_version":"候选规则版本","field":"商品字段名",
   "evidence_span":"字段中的逐字原文","rationale":"风险说明","suggestion":"修改建议","confidence":0.0}
]}
没有发现时返回 {"findings":[]}。每个 finding 只能引用 candidate_rules 中原样提供的
rule_id 和 version；field 必须在该规则的 field_scope 内；evidence_span 必须是相应商品字段中
逐字出现的非空文本；不得增加字段。
""".strip()


class _SemanticPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[SemanticFinding] = Field(default_factory=list)


class SemanticRiskSkill:
    """Validate one structured semantic pass against a bounded RAG candidate set."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        prompt_version: str,
        provider_name: str = "deepseek",
        prompt_name: str = "semantic_risk",
    ) -> None:
        self._llm_provider = llm_provider
        self._prompt_version = prompt_version
        self._provider_name = provider_name
        self._prompt_name = prompt_name

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
                trace_metadata=self._unavailable_trace_metadata(
                    retry_count=0,
                    repair_attempted=False,
                ),
            )

        validation_stage: str | None = None
        for attempt in range(2):
            try:
                try:
                    findings = _SemanticPayload.model_validate(response.payload).findings
                except ValidationError:
                    validation_stage = "payload_schema"
                    raise
                try:
                    issues = self._issues(product, candidates, findings)
                except ValueError:
                    validation_stage = "finding_grounding"
                    raise
                return SemanticSkillResult(
                    issues=issues,
                    trace_metadata=self._trace_metadata(
                        response,
                        retry_count=attempt,
                        schema_valid=True,
                        repair_attempted=attempt == 1,
                    ),
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
                        trace_metadata=self._unavailable_trace_metadata(
                            retry_count=1,
                            repair_attempted=True,
                        ),
                    )
        return SemanticSkillResult(
            degradation_flags=["structured_output_invalid"],
            review_required=True,
            trace_metadata=self._trace_metadata(
                response,
                retry_count=1,
                schema_valid=False,
                repair_attempted=True,
                validation_stage=validation_stage,
            ),
        )

    def _messages(
        self, product: ProductInput, candidates: list[RetrievalCandidate]
    ) -> list[dict[str, str]]:
        prompt = json.loads(_PROMPT_PATH.read_text(encoding="utf-8"))
        return [
            {
                "role": "system",
                "content": f"{prompt['system']}\n{_STRUCTURED_OUTPUT_CONTRACT}",
            },
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

    def _trace_metadata(
        self,
        response: object,
        *,
        retry_count: int,
        schema_valid: bool,
        repair_attempted: bool,
        validation_stage: str | None = None,
    ) -> dict[str, object]:
        from llm.models import LLMResponse

        if not isinstance(response, LLMResponse):
            raise TypeError("LLM provider must return LLMResponse")
        metadata: dict[str, object] = {
            "provider": self._provider_name,
            "prompt_name": self._prompt_name,
            "prompt_version": self._prompt_version,
            "model_name": response.model_name,
            "input_tokens": response.input_tokens,
            "output_tokens": response.output_tokens,
            "latency_ms": response.latency_ms,
            "retry_count": retry_count,
            "schema_valid": schema_valid,
            "repair_attempted": repair_attempted,
        }
        if validation_stage is not None:
            metadata["validation_stage"] = validation_stage
        return metadata

    def _unavailable_trace_metadata(
        self, *, retry_count: int, repair_attempted: bool
    ) -> dict[str, object]:
        return {
            "provider": self._provider_name,
            "prompt_name": self._prompt_name,
            "prompt_version": self._prompt_version,
            "retry_count": retry_count,
            "schema_valid": False,
            "repair_attempted": repair_attempted,
            "error_category": "llm_failed",
        }


class SemanticInspectionSkill:
    """Combine RAG candidate retrieval with the bounded semantic-risk skill."""

    def __init__(self, *, rule_retriever: object, semantic_risk_skill: SemanticRiskSkill) -> None:
        self._rule_retriever = rule_retriever
        self._semantic_risk_skill = semantic_risk_skill

    def inspect(
        self,
        product: ProductInput,
        rules: list[Rule],
        deterministic_issues: list[Issue],
    ) -> SemanticSkillResult:
        try:
            result = self._retrieve(product, rules)
        except RagUnavailableError:
            return SemanticSkillResult(
                degradation_flags=["rag_unavailable"],
                review_required=True,
                trace_metadata={"error_category": "rag_unavailable"},
            )
        semantic_result = self._semantic_risk_skill.inspect(
            product, result.candidates, deterministic_issues
        )
        return SemanticSkillResult(
            issues=semantic_result.issues,
            degradation_flags=semantic_result.degradation_flags,
            review_required=semantic_result.review_required,
            trace_metadata={**result.trace_metadata, **semantic_result.trace_metadata},
        )

    def _retrieve(self, product: ProductInput, rules: list[Rule]) -> RetrievalResult:
        retrieve = getattr(self._rule_retriever, "retrieve", None)
        if not callable(retrieve):
            raise TypeError("semantic inspection requires a rule retriever")
        return retrieve(product, rules)
