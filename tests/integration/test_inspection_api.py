from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from contracts.models import Rule
from db.repositories.rules import RuleRepository
from llm.models import SemanticSkillResult

ROOT = Path(__file__).resolve().parents[2]


def _case_payload(case_id: str) -> dict[str, object]:
    with (ROOT / "evaluation/datasets/food_golden_dataset.json").open(encoding="utf-8") as file:
        cases = json.load(file)
    return next(item for item in cases if item["case_id"] == case_id)["input"]


def _load_rules() -> list[Rule]:
    with (ROOT / "data/rules/food_rules.json").open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


class _RecordingSemanticInspectionSkill:
    def __init__(self) -> None:
        self.call_count = 0

    def inspect(
        self, product: object, rules: list[object], deterministic_issues: list[object]
    ) -> SemanticSkillResult:
        del product, rules, deterministic_issues
        self.call_count += 1
        return SemanticSkillResult(
            trace_metadata={
                "provider": "deepseek",
                "prompt_name": "semantic_risk",
                "prompt_version": "1.0.0",
                "model_name": "deepseek-chat",
                "input_tokens": 10,
                "output_tokens": 5,
                "latency_ms": 20,
                "retry_count": 0,
                "schema_valid": True,
                "repair_attempted": False,
                "candidate_rule_ids": ["food_health_002"],
                "raw_output": "must never be returned",
                "error_message": "must never be returned",
            }
        )


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
    assert client.get("/api/v2/inspections/missing/trace").status_code == 404
    engine.dispose()


def test_inspection_api_uses_request_scoped_semantic_switch_and_safe_trace(
    migrated_test_database: str,
) -> None:
    engine = create_engine(migrated_test_database)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        RuleRepository(session).import_rules(_load_rules())
        session.commit()

    semantic_skill = _RecordingSemanticInspectionSkill()
    client = TestClient(create_app(session_factory, semantic_inspection_skill=semantic_skill))

    disabled_response = client.post(
        "/api/v2/inspections",
        json=_case_payload("food_case_005"),
    )
    assert disabled_response.status_code == 201
    assert semantic_skill.call_count == 0

    enabled_response = client.post(
        "/api/v2/inspections",
        json=_case_payload("food_case_005"),
        headers={"X-Semantic-Inspection": "enabled"},
    )
    assert enabled_response.status_code == 201
    assert semantic_skill.call_count == 1

    invalid_response = client.post(
        "/api/v2/inspections",
        json=_case_payload("food_case_005"),
        headers={"X-Semantic-Inspection": "unexpected"},
    )
    assert invalid_response.status_code == 422
    assert semantic_skill.call_count == 1

    trace_response = client.get(f"/api/v2/inspections/{enabled_response.json()['task_id']}/trace")
    assert trace_response.status_code == 200
    semantic_event = next(
        event
        for event in trace_response.json()["events"]
        if event["step_name"] == "semantic_risk_skill"
    )
    assert semantic_event["metadata"] == {
        "provider": "deepseek",
        "prompt_name": "semantic_risk",
        "prompt_version": "1.0.0",
        "model_name": "deepseek-chat",
        "input_tokens": 10,
        "output_tokens": 5,
        "latency_ms": 20,
        "retry_count": 0,
        "schema_valid": True,
        "repair_attempted": False,
        "candidate_rule_ids": ["food_health_002"],
    }
    assert "raw_output" not in semantic_event["metadata"]
    assert "error_message" not in semantic_event["metadata"]
    engine.dispose()
