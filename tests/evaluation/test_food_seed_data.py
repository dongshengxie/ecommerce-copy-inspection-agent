from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "data/rules/food_rules.json"
CASES_PATH = ROOT / "evaluation/datasets/food_golden_dataset.json"
RULE_KEYS = {
    "rule_id",
    "version",
    "category",
    "field_scope",
    "issue_type",
    "risk_level",
    "rule_strength",
    "rule_text",
    "bad_examples",
    "rewrite_hint",
    "status",
    "effective_at",
}
CASE_KEYS = {
    "case_id",
    "dataset_version",
    "input",
    "expected_issues",
    "expected_risk_level",
    "expected_rule_ids",
    "notes",
}
INPUT_KEYS = {
    "product_id",
    "product_revision",
    "category",
    "title",
    "selling_points",
    "description",
    "attributes",
    "marketing_description",
    "trigger_source",
}


def _load_json(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _issue_value(input_data: dict[str, object], field: str) -> object:
    if field.startswith("attributes."):
        attribute_name = field.removeprefix("attributes.")
        return input_data["attributes"][attribute_name]  # type: ignore[index]
    return input_data[field]


def test_food_seed_data_is_cross_referenced_and_evidence_grounded() -> None:
    rules = _load_json(RULES_PATH)
    cases = _load_json(CASES_PATH)

    assert len(rules) == 10
    assert len(cases) == 10
    assert all(set(rule) == RULE_KEYS for rule in rules)
    assert {rule["category"] for rule in rules} == {"食品"}
    assert all(rule["field_scope"] for rule in rules)
    assert all(rule["status"] == "enabled" for rule in rules)

    rule_ids = {rule["rule_id"] for rule in rules}
    assert len(rule_ids) == len(rules)
    assert Counter(case["expected_risk_level"] for case in cases) == {
        "pass": 2,
        "low": 2,
        "medium": 3,
        "high": 3,
    }
    assert len({case["case_id"] for case in cases}) == len(cases)

    for case in cases:
        assert set(case) == CASE_KEYS
        input_data = case["input"]
        assert set(input_data) == INPUT_KEYS  # type: ignore[arg-type]
        assert input_data["category"] == "食品"  # type: ignore[index]
        expected_rule_ids = case["expected_rule_ids"]
        assert expected_rule_ids == sorted(set(expected_rule_ids))  # type: ignore[arg-type]
        for issue in case["expected_issues"]:  # type: ignore[union-attr]
            assert set(issue["rule_ids"]) <= rule_ids
            assert set(issue["rule_ids"]) <= set(expected_rule_ids)
            field_value = _issue_value(input_data, issue["field"])  # type: ignore[arg-type]
            attribute_name = issue["field"].removeprefix("attributes.")
            assert issue["evidence_span"] in field_value or issue["evidence_span"] == attribute_name


def test_food_seed_data_is_owner_confirmed() -> None:
    cases = _load_json(CASES_PATH)

    assert {case["notes"] for case in cases} == {"项目方已确认的 v1.0 基线"}
