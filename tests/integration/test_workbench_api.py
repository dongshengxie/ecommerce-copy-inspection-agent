from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from contracts.models import Rule
from db.repositories.rules import RuleRepository

ROOT = Path(__file__).resolve().parents[2]


def _submission_payload(case_id: str) -> dict[str, object]:
    with (ROOT / "evaluation/datasets/food_golden_dataset.json").open(encoding="utf-8") as file:
        cases = json.load(file)
    source = next(item for item in cases if item["case_id"] == case_id)["input"]
    return {
        key: value
        for key, value in source.items()
        if key not in {"product_id", "product_revision", "trigger_source"}
    }


def _load_rules() -> list[Rule]:
    with (ROOT / "data/rules/food_rules.json").open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


def test_workbench_submission_creates_food_inspection_with_server_trigger_source(
    migrated_test_database: str,
) -> None:
    engine = create_engine(migrated_test_database)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        RuleRepository(session).import_rules(_load_rules())
        session.commit()

    client = TestClient(create_app(session_factory))
    response = client.post(
        "/api/v2/workbench/inspections",
        json=_submission_payload("food_case_005"),
    )

    assert response.status_code == 201
    created = response.json()
    assert created["status"] == "success"
    assert created["result_url"] == f"/api/v2/inspections/{created['task_id']}/result"

    task_response = client.get(f"/api/v2/inspections/{created['task_id']}")
    assert task_response.status_code == 200
    assert task_response.json()["trigger_source"] == "vue_workbench"
    engine.dispose()
