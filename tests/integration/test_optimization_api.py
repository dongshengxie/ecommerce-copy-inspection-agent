from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.main import create_app
from contracts.models import Rule
from db.models.core import OptimizationAttemptModel
from db.repositories.rules import RuleRepository
from llm.copy_optimization import CopyOptimizationSkill
from llm.models import LLMResponse, SemanticSkillResult

ROOT = Path(__file__).resolve().parents[2]


def _case_payload(case_id: str) -> dict[str, object]:
    with (ROOT / "evaluation/datasets/food_golden_dataset.json").open(encoding="utf-8") as file:
        cases = json.load(file)
    return next(item for item in cases if item["case_id"] == case_id)["input"]


def _load_rules() -> list[Rule]:
    with (ROOT / "data/rules/food_rules.json").open(encoding="utf-8") as file:
        return [Rule.model_validate(item) for item in json.load(file)]


class _FakeLLM:
    def __init__(self, payloads: list[dict[str, object]]) -> None:
        self._payloads = payloads
        self.call_count = 0

    def complete_structured(self, messages: list[dict[str, str]]) -> LLMResponse:
        assert messages[0]["role"] == "system"
        payload = self._payloads[self.call_count]
        self.call_count += 1
        return LLMResponse(
            payload=payload,
            model_name="deepseek-chat",
            input_tokens=12,
            output_tokens=8,
            latency_ms=20,
        )


class _NoIssueSemanticSkill:
    def inspect(
        self, product: object, rules: list[object], deterministic_issues: list[object]
    ) -> SemanticSkillResult:
        del product, rules, deterministic_issues
        return SemanticSkillResult()


def _client(
    migrated_test_database: str, llm: _FakeLLM, *, semantic_enabled: bool = True
) -> tuple[TestClient, sessionmaker]:
    engine = create_engine(migrated_test_database)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory() as session:
        RuleRepository(session).import_rules(_load_rules())
        session.commit()
    return (
        TestClient(
            create_app(
                session_factory,
                semantic_inspection_skill=(_NoIssueSemanticSkill() if semantic_enabled else None),
                copy_optimization_skill=CopyOptimizationSkill(
                    llm_provider=llm,
                    prompt_version="1.0.0",
                ),
            )
        ),
        session_factory,
    )


def test_optimization_requires_successful_source_task_and_matching_issue_field(
    migrated_test_database: str,
) -> None:
    client, _ = _client(
        migrated_test_database,
        _FakeLLM([{"optimized_fields": {"description": "清香口感。"}}]),
    )
    pass_task = client.post("/api/v2/inspections", json=_case_payload("food_case_001")).json()[
        "task_id"
    ]

    assert (
        client.post(
            "/api/v2/inspections/missing/optimization", json={"fields": ["description"]}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v2/inspections/{pass_task}/optimization", json={"fields": ["description"]}
        ).status_code
        == 409
    )


def test_optimization_success_persists_independent_attempt_and_keeps_source_report(
    migrated_test_database: str,
) -> None:
    llm = _FakeLLM([{"optimized_fields": {"description": "香浓谷物口感，适合日常冲泡饮用。"}}])
    client, session_factory = _client(migrated_test_database, llm)
    source_task = client.post("/api/v2/inspections", json=_case_payload("food_case_005")).json()[
        "task_id"
    ]
    source_report = client.get(f"/api/v2/inspections/{source_task}/result").json()

    response = client.post(
        f"/api/v2/inspections/{source_task}/optimization",
        json={"fields": ["description"]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["optimized_fields"] == {
        "description": "香浓谷物口感，适合日常冲泡饮用。"
    }
    assert response.json()["verification_report"]["automated_risk_level"] == "pass"
    assert client.get(f"/api/v2/inspections/{source_task}/result").json() == source_report
    with session_factory() as session:
        assert (
            session.scalar(select(OptimizationAttemptModel.id))
            == response.json()["optimization_id"]
        )


def test_optimization_verification_rewrites_once_then_stops(
    migrated_test_database: str,
) -> None:
    llm = _FakeLLM(
        [
            {"optimized_fields": {"description": "本产品可有效治疗失眠，睡前冲泡即可。"}},
            {"optimized_fields": {"description": "本产品可有效治疗失眠，睡前冲泡即可。"}},
        ]
    )
    client, _ = _client(migrated_test_database, llm)
    source_task = client.post("/api/v2/inspections", json=_case_payload("food_case_002")).json()[
        "task_id"
    ]
    source_report = client.get(f"/api/v2/inspections/{source_task}/result").json()

    response = client.post(
        f"/api/v2/inspections/{source_task}/optimization",
        json={"fields": ["description"]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "verification_failed"
    assert response.json()["verification_report"]["review_required"] is True
    assert llm.call_count == 2
    assert client.get(f"/api/v2/inspections/{source_task}/result").json() == source_report
    trace = client.get(f"/api/v2/inspections/{source_task}/trace").json()["events"]
    operations = [
        (event["metadata"]["operation"], event["metadata"]["attempt"])
        for event in trace
        if "operation" in event["metadata"]
    ]
    assert operations == [
        ("copy_optimization", 1),
        ("optimization_verification", 1),
        ("copy_optimization", 2),
        ("optimization_verification", 2),
    ]


def test_optimization_cannot_succeed_when_semantic_verification_is_unavailable(
    migrated_test_database: str,
) -> None:
    client, _ = _client(
        migrated_test_database,
        _FakeLLM(
            [
                {"optimized_fields": {"description": "香浓谷物口感，适合日常冲泡饮用。"}},
                {"optimized_fields": {"description": "香浓谷物口感，适合日常冲泡饮用。"}},
            ]
        ),
        semantic_enabled=False,
    )
    source_task = client.post("/api/v2/inspections", json=_case_payload("food_case_005")).json()[
        "task_id"
    ]

    response = client.post(
        f"/api/v2/inspections/{source_task}/optimization",
        json={"fields": ["description"]},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "verification_failed"
    assert "degradation" in response.json()["failure_reason"]
