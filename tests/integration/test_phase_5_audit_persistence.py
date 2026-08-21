from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import sessionmaker

from app.services.inspection import InspectionApplicationService
from contracts.models import ProductInput, Rule
from contracts.optimization import OptimizationResult
from db.models.core import OptimizationAttemptModel, ProductRevisionModel, QualityRuleModel
from db.repositories.inspections import InspectionRepository
from db.repositories.optimizations import OptimizationRepository
from db.repositories.rules import RuleRepository

ROOT = Path(__file__).resolve().parents[2]


def _case_input(case_id: str) -> ProductInput:
    with (ROOT / "evaluation/datasets/food_golden_dataset.json").open(encoding="utf-8") as file:
        cases = json.load(file)
    return ProductInput.model_validate(
        next(case for case in cases if case["case_id"] == case_id)["input"]
    )


def _load_rules() -> list[Rule]:
    with (ROOT / "data/rules/food_rules.json").open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


def test_completed_task_keeps_exact_loaded_rule_version_after_rule_is_disabled(
    migrated_test_database: str,
) -> None:
    engine = create_engine(migrated_test_database)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        RuleRepository(session).import_rules(_load_rules())
        session.commit()

    report = InspectionApplicationService(session_factory).create_inspection(
        _case_input("food_case_005")
    )

    with session_factory() as session:
        session.execute(
            update(QualityRuleModel)
            .where(QualityRuleModel.rule_id == "food_health_002")
            .values(status="disabled")
        )
        session.commit()
        references = InspectionRepository(session).get_task_rule_references(report.task_id)

    assert ("food_health_002", "1.1.0") in {
        (reference.rule_id, reference.rule_version) for reference in references
    }
    engine.dispose()


def test_optimization_attempt_persists_without_creating_product_revision(
    migrated_test_database: str,
) -> None:
    engine = create_engine(migrated_test_database)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        RuleRepository(session).import_rules(_load_rules())
        session.commit()

    report = InspectionApplicationService(session_factory).create_inspection(
        _case_input("food_case_005")
    )

    with session_factory() as session:
        original_revision_count = session.scalar(select(func.count(ProductRevisionModel.id)))
        OptimizationRepository(session).create_attempt(
            OptimizationResult(
                optimization_id="opt-001",
                source_task_id=report.task_id,
                status="failed",
                requested_fields=["description"],
                failure_reason="llm_failed",
            )
        )
        session.commit()

        assert session.scalar(select(func.count(OptimizationAttemptModel.id))) == 1
        assert (
            session.scalar(select(func.count(ProductRevisionModel.id))) == original_revision_count
        )
    engine.dispose()
