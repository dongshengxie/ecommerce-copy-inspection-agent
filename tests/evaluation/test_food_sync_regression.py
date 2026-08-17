from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.services.inspection import InspectionApplicationService
from contracts.models import ProductInput, Rule
from db.repositories.rules import RuleRepository

ROOT = Path(__file__).resolve().parents[2]


def _load_cases() -> list[dict[str, object]]:
    with (ROOT / "evaluation/datasets/food_golden_dataset.json").open(encoding="utf-8") as file:
        return json.load(file)


def _load_rules() -> list[Rule]:
    with (ROOT / "data/rules/food_rules.json").open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


def _normalize_issues(issues: list[object]) -> list[dict[str, object]]:
    return [
        {
            "field": issue.field,
            "issue_type": issue.issue_type,
            "risk_level": issue.risk_level.value,
            "evidence_span": issue.evidence_span,
            "rule_ids": sorted(issue.rule_ids),
        }
        for issue in issues
    ]


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["case_id"])
def test_food_golden_dataset_matches_synchronous_inspection(
    case: dict[str, object], migrated_test_database: str
) -> None:
    engine = create_engine(migrated_test_database)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        RuleRepository(session).import_rules(_load_rules())
        session.commit()

    report = InspectionApplicationService(session_factory).create_inspection(
        ProductInput.model_validate(case["input"])
    )

    assert report.automated_risk_level.value == case["expected_risk_level"]
    assert _normalize_issues(report.issues) == case["expected_issues"]
    assert (
        sorted({rule_id for issue in report.issues for rule_id in issue.rule_ids})
        == case["expected_rule_ids"]
    )
    engine.dispose()
