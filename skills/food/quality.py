from contracts.models import ProductInput, Rule, SkillResult
from tools.food.checks import (
    check_food_spec_consistency,
    check_required_food_attributes,
    check_rule_expressions,
)

FIELD_ORDER = {
    "title": 0,
    "selling_points": 1,
    "description": 2,
    "attributes.ingredients": 3,
    "attributes.shelf_life": 4,
    "attributes.storage_method": 5,
    "attributes.origin": 6,
    "attributes.net_content": 7,
    "marketing_description": 8,
}


class FoodQualitySkill:
    """Compose deterministic Food Tools without database, LLM, or workflow access."""

    def inspect(self, product: ProductInput, rules: list[Rule]) -> SkillResult:
        tool_results = [
            check_rule_expressions(product, rules),
            check_required_food_attributes(product, rules),
            check_food_spec_consistency(product, rules),
        ]
        issues = [issue for result in tool_results for issue in result.issues]
        return SkillResult(
            name="food_quality_skill",
            status="success",
            issues=sorted(
                issues,
                key=lambda issue: (FIELD_ORDER.get(issue.field, len(FIELD_ORDER)), issue.rule_ids),
            ),
            warnings=[warning for result in tool_results for warning in result.warnings],
        )
