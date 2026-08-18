from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from app.config import Settings
from evaluation.models import GoldenCase
from evaluation.runner import (
    parse_cli_arguments,
    run_live,
    run_offline,
    write_result,
)


def _case() -> GoldenCase:
    return GoldenCase.model_validate(
        {
            "case_id": "case-1",
            "dataset_version": "1.0.0",
            "input": {
                "product_id": "product-1",
                "product_revision": 1,
                "category": "食品",
                "title": "草本风味袋泡茶 30g",
                "selling_points": ["独立包装"],
                "description": "清香口感。",
                "attributes": {
                    "ingredients": "绿茶",
                    "shelf_life": "12个月",
                    "storage_method": "阴凉干燥处保存",
                    "origin": "浙江",
                },
                "marketing_description": "30g 盒装。",
                "trigger_source": "evaluation",
            },
            "expected_issues": [],
            "expected_risk_level": "pass",
            "expected_rule_ids": [],
            "notes": "项目方已确认的 v1.0 基线",
        }
    )


def _settings(**overrides: str) -> Settings:
    values = {
        "mysql_host": "127.0.0.1",
        "mysql_port": 3307,
        "mysql_database": "app",
        "mysql_user": "app",
        "mysql_password": "password",
        "mysql_test_database": "app_test",
        "elasticsearch_url": "http://127.0.0.1:9200",
        "elasticsearch_index_prefix": "food_rules",
        "bge_api_base_url": "https://api.example.com",
        "bge_api_key": "bge-key",
        "bge_embedding_model": "embedding-model",
        "bge_reranker_model": "reranker-model",
        "deepseek_api_key": "deepseek-key",
        "deepseek_model": "deepseek-chat",
    }
    values.update(overrides)
    return Settings(**values)


def test_offline_runner_uses_no_network_or_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "Client", lambda: pytest.fail("network must not be constructed"))

    result = run_offline(
        cases=[_case()],
        rules=[],
        now=datetime(2026, 8, 18, tzinfo=UTC),
    )

    assert result.mode == "offline"
    assert result.metrics["task_success_rate"] == 1.0
    assert result.case_results[0].observed_risk_level == "pass"


def test_live_runner_rejects_missing_bge_or_deepseek_configuration() -> None:
    with pytest.raises(ValueError, match="BGE_API_KEY"):
        run_live(
            cases=[],
            settings=_settings(bge_api_key=""),
            api_base_url="http://127.0.0.1:8000",
            http_client=None,
        )


def test_candidate_runner_requires_baseline_path() -> None:
    with pytest.raises(ValueError, match="baseline"):
        parse_cli_arguments(["--candidate"])


def test_result_file_excludes_product_text_and_includes_versions(tmp_path) -> None:
    result = run_offline(
        cases=[_case()],
        rules=[],
        now=datetime(2026, 8, 18, tzinfo=UTC),
    )

    path = write_result(result, tmp_path, now=datetime(2026, 8, 18, tzinfo=UTC))
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert set(payload["versions"]) == {
        "dataset",
        "rule",
        "prompt",
        "model",
        "embedding",
        "reranker",
        "threshold",
    }
    assert "草本风味" not in path.read_text(encoding="utf-8")
