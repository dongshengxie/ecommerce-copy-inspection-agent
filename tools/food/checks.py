from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal

from contracts.models import Issue, ProductInput, Rule, ToolResult

ATTRIBUTE_RULE_IDS = {
    "ingredients": "food_attribute_005",
    "shelf_life": "food_attribute_006",
    "storage_method": "food_attribute_007",
    "origin": "food_attribute_008",
}
TEXT_FIELDS = ("title", "selling_points", "description", "marketing_description")
SPECIFICATION_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kg|g|ml|l|千克|克|毫升|升|袋|包|盒)",
    re.IGNORECASE,
)


def _enabled_rules_by_id(rules: Iterable[Rule]) -> dict[str, Rule]:
    return {rule.rule_id: rule for rule in rules if rule.status == "enabled"}


def _issue(
    rule: Rule,
    *,
    field: str,
    evidence_span: str,
    evidence: str,
    source: str,
) -> Issue:
    return Issue(
        field=field,
        issue_type=rule.issue_type,
        risk_level=rule.risk_level,
        evidence_span=evidence_span,
        evidence=evidence,
        rule_ids=[rule.rule_id],
        source=[source],
        confidence=1.0,
        suggestion=rule.rewrite_hint,
    )


def _field_values(product: ProductInput, field: str) -> list[str]:
    value = getattr(product, field)
    if isinstance(value, list):
        return value
    return [value]


def check_rule_expressions(product: ProductInput, rules: list[Rule]) -> ToolResult:
    """Find literal supplied examples only within each rule's allowed text fields."""
    issues: list[Issue] = []
    for rule in rules:
        if rule.status != "enabled":
            continue
        for field in rule.field_scope:
            if field not in TEXT_FIELDS:
                continue
            for value in _field_values(product, field):
                for bad_example in rule.bad_examples:
                    if bad_example in value:
                        issues.append(
                            _issue(
                                rule,
                                field=field,
                                evidence_span=bad_example,
                                evidence=value,
                                source="food_rule_expression_check",
                            )
                        )
    return ToolResult(name="food_rule_expression_check", status="success", issues=issues)


def check_required_food_attributes(product: ProductInput, rules: list[Rule]) -> ToolResult:
    """Report blank required food attributes through their supplied rules."""
    enabled_rules = _enabled_rules_by_id(rules)
    issues: list[Issue] = []
    for attribute_name, rule_id in ATTRIBUTE_RULE_IDS.items():
        value = getattr(product.attributes, attribute_name)
        rule = enabled_rules.get(rule_id)
        if rule is not None and not value.strip():
            issues.append(
                _issue(
                    rule,
                    field=f"attributes.{attribute_name}",
                    evidence_span=attribute_name,
                    evidence=attribute_name,
                    source="food_required_attribute_check",
                )
            )
    return ToolResult(name="food_required_attribute_check", status="success", issues=issues)


def _specifications(product: ProductInput) -> list[tuple[str, str, Decimal, str]]:
    fields = [("title", product.title), ("description", product.description)]
    if product.attributes.net_content:
        fields.append(("attributes.net_content", product.attributes.net_content))

    matches: list[tuple[str, str, Decimal, str]] = []
    for field, value in fields:
        for match in SPECIFICATION_PATTERN.finditer(value):
            unit = match.group("unit").lower()
            matches.append((field, match.group(0), Decimal(match.group("value")), unit))
    return matches


def check_food_spec_consistency(product: ProductInput, rules: list[Rule]) -> ToolResult:
    """Compare literal same-unit specifications across title, description, and net content."""
    rule = _enabled_rules_by_id(rules).get("food_spec_009")
    if rule is None:
        return ToolResult(name="food_spec_consistency_check", status="success")

    specifications = _specifications(product)
    for index, (field, evidence_span, value, unit) in enumerate(specifications):
        for _, _, other_value, other_unit in specifications[index + 1 :]:
            if unit == other_unit and value != other_value:
                issue = _issue(
                    rule,
                    field=field,
                    evidence_span=evidence_span,
                    evidence=evidence_span,
                    source="food_spec_consistency_check",
                )
                return ToolResult(
                    name="food_spec_consistency_check", status="success", issues=[issue]
                )
    return ToolResult(name="food_spec_consistency_check", status="success")
