from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from contracts.models import InspectionReport, ProductInput, Rule
from contracts.optimization import OptimizationRequest, WritableCopyField
from llm.models import LLMResponse
from llm.providers import LLMProvider, LLMUnavailableError

_PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "copy_optimization" / "1.0.0.json"
_SPECIFICATION_PATTERN = re.compile(
    r"(?i)\d+(?:\.\d+)?\s*(?:kg|g|ml|l|千克|克|毫升|升|袋|盒|罐|片|粒|包)"
)
_ATTRIBUTE_CLAIM_PATTERNS = {
    "ingredients": re.compile(r"配料\s*(?:为|是|[:：])"),
    "shelf_life": re.compile(r"保质期\s*(?:为|是|[:：])"),
    "storage_method": re.compile(r"(?:储存方式|保存方式)\s*(?:为|是|[:：])"),
    "origin": re.compile(r"产地\s*(?:为|是|[:：])"),
}


class _CopyOptimizationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    optimized_fields: dict[str, object] = Field(min_length=1)


@dataclass(frozen=True)
class CopyOptimizationArtifact:
    """Validated generated fields plus safe call metadata for one rewrite attempt."""

    optimized_fields: dict[WritableCopyField, str | list[str]] = field(default_factory=dict)
    referenced_rule_ids: list[str] = field(default_factory=list)
    failure_reason: str | None = None
    safe_metadata: dict[str, object] = field(default_factory=dict)


class CopyOptimizationSkill:
    """Generate only explicitly requested food-copy edits with fact-boundary validation."""

    def __init__(
        self,
        *,
        llm_provider: LLMProvider,
        prompt_version: str,
        provider_name: str = "deepseek",
        prompt_name: str = "copy_optimization",
    ) -> None:
        self._llm_provider = llm_provider
        self._prompt_version = prompt_version
        self._provider_name = provider_name
        self._prompt_name = prompt_name

    def optimize(
        self,
        product: ProductInput,
        report: InspectionReport,
        rules: list[Rule],
        request: OptimizationRequest,
        *,
        failure_reasons: list[str] | None = None,
        previous_optimized_fields: dict[WritableCopyField, str | list[str]] | None = None,
    ) -> CopyOptimizationArtifact:
        """Return one validated rewrite, or a recoverable failed artifact after one repair."""
        referenced_rule_ids = self._referenced_rule_ids(report, request)
        messages = self._messages(
            product,
            report,
            rules,
            request,
            referenced_rule_ids=referenced_rule_ids,
            failure_reasons=failure_reasons,
            previous_optimized_fields=previous_optimized_fields,
        )
        try:
            response = self._llm_provider.complete_structured(messages)
        except LLMUnavailableError:
            return CopyOptimizationArtifact(
                referenced_rule_ids=referenced_rule_ids,
                failure_reason="llm_failed",
                safe_metadata=self._unavailable_metadata(
                    retry_count=0,
                    repair_attempted=False,
                ),
            )

        for attempt in range(2):
            try:
                optimized_fields = self._validated_fields(response.payload, product, request)
                return CopyOptimizationArtifact(
                    optimized_fields=optimized_fields,
                    referenced_rule_ids=referenced_rule_ids,
                    safe_metadata=self._response_metadata(
                        response,
                        retry_count=attempt,
                        schema_valid=True,
                        repair_attempted=attempt == 1,
                    ),
                )
            except (ValidationError, ValueError, TypeError):
                if attempt == 1:
                    break
                try:
                    response = self._llm_provider.complete_structured(
                        messages
                        + [
                            {
                                "role": "user",
                                "content": (
                                    "上一次输出不符合优化字段与事实保护要求，请仅返回合规 JSON。"
                                ),
                            }
                        ]
                    )
                except LLMUnavailableError:
                    return CopyOptimizationArtifact(
                        referenced_rule_ids=referenced_rule_ids,
                        failure_reason="llm_failed",
                        safe_metadata=self._unavailable_metadata(
                            retry_count=1,
                            repair_attempted=True,
                        ),
                    )
        return CopyOptimizationArtifact(
            referenced_rule_ids=referenced_rule_ids,
            failure_reason="optimization_output_invalid",
            safe_metadata=self._response_metadata(
                response,
                retry_count=1,
                schema_valid=False,
                repair_attempted=True,
            ),
        )

    def _messages(
        self,
        product: ProductInput,
        report: InspectionReport,
        rules: list[Rule],
        request: OptimizationRequest,
        *,
        referenced_rule_ids: list[str],
        failure_reasons: list[str] | None,
        previous_optimized_fields: dict[WritableCopyField, str | list[str]] | None,
    ) -> list[dict[str, str]]:
        prompt = json.loads(_PROMPT_PATH.read_text(encoding="utf-8"))
        selected_issues = [issue for issue in report.issues if issue.field in request.fields]
        selected_rules = [rule for rule in rules if rule.rule_id in referenced_rule_ids]
        return [
            {"role": "system", "content": str(prompt["system"])},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "requested_fields": {
                            field: self._field_value(product, field) for field in request.fields
                        },
                        "immutable_attributes": product.attributes.model_dump(mode="json"),
                        "issues": [
                            {
                                "field": issue.field,
                                "evidence_span": issue.evidence_span,
                                "rule_ids": issue.rule_ids,
                                "suggestion": issue.suggestion,
                            }
                            for issue in selected_issues
                        ],
                        "rules": [
                            {
                                "rule_id": rule.rule_id,
                                "version": rule.version,
                                "field_scope": rule.field_scope,
                                "rule_text": rule.rule_text,
                                "rewrite_hint": rule.rewrite_hint,
                            }
                            for rule in selected_rules
                        ],
                        "previous_optimized_fields": previous_optimized_fields,
                        "verification_failure_reasons": failure_reasons or [],
                    },
                    ensure_ascii=False,
                ),
            },
        ]

    def _validated_fields(
        self,
        payload: object,
        product: ProductInput,
        request: OptimizationRequest,
    ) -> dict[WritableCopyField, str | list[str]]:
        if not isinstance(payload, dict):
            raise ValueError("optimization response must be an object")
        fields = _CopyOptimizationPayload.model_validate(payload).optimized_fields
        if set(fields) != set(request.fields):
            raise ValueError("optimization response fields do not match request")

        validated: dict[WritableCopyField, str | list[str]] = {}
        known_specifications = self._specifications(
            "\n".join(
                [
                    product.title,
                    product.description,
                    product.attributes.ingredients,
                    product.attributes.shelf_life,
                    product.attributes.storage_method,
                    product.attributes.origin,
                    *(
                        value
                        for value in product.attributes.model_dump().values()
                        if isinstance(value, str)
                    ),
                ]
            )
        )
        for requested_field in request.fields:
            value = fields[requested_field]
            if requested_field == "selling_points":
                if (
                    not isinstance(value, list)
                    or not value
                    or not all(isinstance(item, str) and item.strip() for item in value)
                ):
                    raise ValueError("selling_points must contain non-empty strings")
                output: str | list[str] = value
                output_text = "\n".join(value)
            else:
                if not isinstance(value, str) or not value.strip():
                    raise ValueError("text fields must be non-empty strings")
                output = value
                output_text = value
                if requested_field in {"title", "description"}:
                    protected = self._specifications(
                        str(self._field_value(product, requested_field))
                    )
                    if not protected.issubset(self._specifications(output_text)):
                        raise ValueError("protected specification is missing")

            output_specifications = self._specifications(output_text)
            if not output_specifications.issubset(known_specifications):
                raise ValueError("optimization output introduces an unknown specification")
            self._validate_attribute_claims(output_text, product)
            validated[requested_field] = output
        return validated

    @staticmethod
    def _field_value(product: ProductInput, field: WritableCopyField) -> str | list[str]:
        return getattr(product, field)

    @staticmethod
    def _specifications(value: str) -> set[str]:
        return {
            match.group(0).replace(" ", "").lower()
            for match in _SPECIFICATION_PATTERN.finditer(value)
        }

    @staticmethod
    def _validate_attribute_claims(output_text: str, product: ProductInput) -> None:
        for attribute_name, pattern in _ATTRIBUTE_CLAIM_PATTERNS.items():
            attribute_value = getattr(product.attributes, attribute_name)
            if pattern.search(output_text) and attribute_value not in output_text:
                raise ValueError("optimization output conflicts with a protected attribute")

    @staticmethod
    def _referenced_rule_ids(report: InspectionReport, request: OptimizationRequest) -> list[str]:
        return sorted(
            {
                rule_id
                for issue in report.issues
                if issue.field in request.fields
                for rule_id in issue.rule_ids
            }
        )

    def _response_metadata(
        self,
        response: LLMResponse,
        *,
        retry_count: int,
        schema_valid: bool,
        repair_attempted: bool,
    ) -> dict[str, object]:
        return {
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
            "operation": "copy_optimization",
        }

    def _unavailable_metadata(
        self, *, retry_count: int, repair_attempted: bool
    ) -> dict[str, object]:
        return {
            "provider": self._provider_name,
            "prompt_name": self._prompt_name,
            "prompt_version": self._prompt_version,
            "retry_count": retry_count,
            "schema_valid": False,
            "repair_attempted": repair_attempted,
            "operation": "copy_optimization",
            "error_category": "llm_failed",
        }
