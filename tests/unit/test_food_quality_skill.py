from __future__ import annotations

import json
from pathlib import Path

from contracts.models import ProductInput, Rule
from skills.food.quality import FoodQualitySkill

ROOT = Path(__file__).resolve().parents[2]


def _rules() -> list[Rule]:
    with (ROOT / "data/rules/food_rules.json").open(encoding="utf-8") as file:
        return sorted(
            (Rule.model_validate(item) for item in json.load(file)),
            key=lambda rule: rule.rule_id,
        )


def _case_input(case_id: str) -> ProductInput:
    with (ROOT / "evaluation/datasets/food_golden_dataset.json").open(encoding="utf-8") as file:
        cases = json.load(file)
    case = next(item for item in cases if item["case_id"] == case_id)
    return ProductInput.model_validate(case["input"])


def test_food_quality_skill_returns_no_findings_for_case_001() -> None:
    result = FoodQualitySkill().inspect(_case_input("food_case_001"), _rules())

    assert result.issues == []


def test_food_quality_skill_combines_six_case_004_findings() -> None:
    result = FoodQualitySkill().inspect(_case_input("food_case_004"), _rules())

    assert [(issue.field, issue.rule_ids) for issue in result.issues] == [
        ("title", ["food_claim_001"]),
        ("description", ["food_absolute_003"]),
        ("description", ["food_audience_004"]),
        ("attributes.ingredients", ["food_attribute_005"]),
        ("attributes.shelf_life", ["food_attribute_006"]),
        ("attributes.origin", ["food_attribute_008"]),
    ]
