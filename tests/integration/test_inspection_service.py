from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.services.inspection import InspectionApplicationService
from contracts.models import ProductInput, RiskLevel, Rule, TaskStatus
from db.models.core import AgentTraceModel, InspectionIssueModel, InspectionResultModel
from db.repositories.rules import RuleRepository

ROOT = Path(__file__).resolve().parents[2]


def _case_input(case_id: str) -> ProductInput:
    with (ROOT / "evaluation/datasets/food_golden_dataset.json").open(encoding="utf-8") as file:
        cases = json.load(file)
    case = next(item for item in cases if item["case_id"] == case_id)
    return ProductInput.model_validate(case["input"])


def _load_rules() -> list[Rule]:
    with (ROOT / "data/rules/food_rules.json").open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


def test_inspection_service_persists_case_004_report_issues_and_traces(
    migrated_test_database: str,
) -> None:
    engine = create_engine(migrated_test_database)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        RuleRepository(session).import_rules(_load_rules())
        session.commit()

    report = InspectionApplicationService(session_factory).create_inspection(
        _case_input("food_case_004")
    )

    assert report.status is TaskStatus.SUCCESS
    assert report.automated_risk_level is RiskLevel.HIGH
    assert report.review_required is True
    assert len(report.issues) == 6

    with session_factory() as session:
        assert session.scalar(select(InspectionResultModel.task_id)) == report.task_id
        assert len(session.scalars(select(InspectionIssueModel)).all()) == 6
        assert {trace.step_name for trace in session.scalars(select(AgentTraceModel)).all()} == {
            "load_rules",
            "food_quality_skill",
            "semantic_risk_skill",
            "issue_fusion",
            "risk_aggregator",
            "report_builder",
        }
    engine.dispose()
