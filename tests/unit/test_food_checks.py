from __future__ import annotations

import json
from pathlib import Path

from contracts.models import ProductInput, Rule
from tools.food.checks import (
    check_food_spec_consistency,
    check_required_food_attributes,
    check_rule_expressions,
)

ROOT = Path(__file__).resolve().parents[2]


def _rules() -> list[Rule]:
    path = ROOT / "data/rules/food_rules.json"
    with path.open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


def _case_input(case_id: str) -> ProductInput:
    path = ROOT / "evaluation/datasets/food_golden_dataset.json"
    with path.open(encoding="utf-8") as file:
        cases = json.load(file)
    case = next(item for item in cases if item["case_id"] == case_id)
    return ProductInput.model_validate(case["input"])


def test_rule_expression_check_finds_case_002_medical_claim() -> None:
    result = check_rule_expressions(_case_input("food_case_002"), _rules())

    assert [(issue.field, issue.evidence_span, issue.rule_ids) for issue in result.issues] == [
        ("description", "治疗失眠", ["food_claim_001"])
    ]
    assert result.issues[0].confidence == 1.0


def test_required_attribute_check_finds_case_004_three_missing_values() -> None:
    result = check_required_food_attributes(_case_input("food_case_004"), _rules())

    assert [(issue.field, issue.evidence_span, issue.rule_ids) for issue in result.issues] == [
        ("attributes.ingredients", "ingredients", ["food_attribute_005"]),
        ("attributes.shelf_life", "shelf_life", ["food_attribute_006"]),
        ("attributes.origin", "origin", ["food_attribute_008"]),
    ]


def test_spec_consistency_check_finds_case_007_500g_and_250g_conflict() -> None:
    result = check_food_spec_consistency(_case_input("food_case_007"), _rules())

    assert [(issue.field, issue.evidence_span, issue.rule_ids) for issue in result.issues] == [
        ("title", "500g", ["food_spec_009"])
    ]
