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


def _case_payload(case_id: str) -> dict[str, object]:
    with (ROOT / "evaluation/datasets/food_golden_dataset.json").open(encoding="utf-8") as file:
        cases = json.load(file)
    return next(item for item in cases if item["case_id"] == case_id)["input"]


def _load_rules() -> list[Rule]:
    with (ROOT / "data/rules/food_rules.json").open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


def test_inspection_api_creates_and_reads_case_005_medium_result(
    migrated_test_database: str,
) -> None:
    engine = create_engine(migrated_test_database)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        RuleRepository(session).import_rules(_load_rules())
        session.commit()

    client = TestClient(create_app(session_factory))
    create_response = client.post("/api/v2/inspections", json=_case_payload("food_case_005"))

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["status"] == "success"
    assert created["result_url"] == f"/api/v2/inspections/{created['task_id']}/result"

    task_response = client.get(f"/api/v2/inspections/{created['task_id']}")
    assert task_response.status_code == 200
    assert task_response.json()["status"] == "success"

    result_response = client.get(created["result_url"])
    assert result_response.status_code == 200
    assert result_response.json()["automated_risk_level"] == "medium"
    engine.dispose()


def test_inspection_api_rejects_non_food_payload(migrated_test_database: str) -> None:
    engine = create_engine(migrated_test_database)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    payload = _case_payload("food_case_005")
    payload["category"] = "美妆"

    response = TestClient(create_app(session_factory)).post("/api/v2/inspections", json=payload)

    assert response.status_code == 422
    engine.dispose()


def test_inspection_api_returns_404_for_unknown_task(migrated_test_database: str) -> None:
    engine = create_engine(migrated_test_database)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    client = TestClient(create_app(session_factory))

    assert client.get("/api/v2/inspections/missing").status_code == 404
    assert client.get("/api/v2/inspections/missing/result").status_code == 404
    engine.dispose()
