from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import httpx

from agent.graph.food_inspection_workflow import FoodInspectionWorkflow
from app.config import Settings
from contracts.models import InspectionReport, Issue, RiskLevel, Rule, TraceEvent
from evaluation.metrics import build_output_diff, compute_metrics, normalize_issue
from evaluation.models import (
    EvaluationCaseResult,
    EvaluationRunResult,
    GoldenCase,
    NormalizedIssue,
)
from skills.food.quality import FoodQualitySkill


def run_offline(
    *, cases: list[GoldenCase], rules: list[Rule], now: datetime
) -> EvaluationRunResult:
    """Evaluate the fixed deterministic food workflow without I/O dependencies."""
    del now
    dataset_version = _dataset_version(cases)
    workflow = FoodInspectionWorkflow(
        rule_loader=lambda: list(rules),
        food_quality_skill=FoodQualitySkill(),
        semantic_inspection_skill=None,
    )
    case_results: list[EvaluationCaseResult] = []
    for case in cases:
        started_at = perf_counter()
        workflow_result = workflow.invoke(task_id=f"evaluation:{case.case_id}", product=case.input)
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        case_results.append(
            _case_result(
                case,
                workflow_result.report,
                workflow_result.trace_events,
                latency_ms=elapsed_ms,
            )
        )
    return _run_result(
        mode="offline",
        dataset_version=dataset_version,
        versions={
            "dataset": dataset_version,
            "rule": _rule_versions(rules),
            "prompt": None,
            "model": None,
            "embedding": None,
            "reranker": None,
            "threshold": None,
        },
        case_results=case_results,
    )


def run_live(
    *,
    cases: list[GoldenCase],
    settings: Settings,
    api_base_url: str,
    http_client: httpx.Client | None,
) -> EvaluationRunResult:
    """Evaluate through FastAPI with semantic inspection explicitly enabled."""
    _require_live_configuration(settings)
    dataset_version = _dataset_version(cases)
    client = http_client or httpx.Client()
    owns_client = http_client is None
    base_url = api_base_url.rstrip("/")
    case_results: list[EvaluationCaseResult] = []
    rule_versions: set[str] = set()
    semantic_metadata: list[dict[str, object]] = []
    try:
        for case in cases:
            started_at = perf_counter()
            created = _request_json(
                client.post(
                    f"{base_url}/api/v2/inspections",
                    json=case.input.model_dump(mode="json"),
                    headers={"X-Semantic-Inspection": "enabled"},
                )
            )
            task_id = str(created["task_id"])
            report = InspectionReport.model_validate(
                _request_json(client.get(f"{base_url}/api/v2/inspections/{task_id}/result"))
            )
            task = _request_json(client.get(f"{base_url}/api/v2/inspections/{task_id}"))
            rule_version = task.get("rule_version")
            if isinstance(rule_version, str):
                rule_versions.add(rule_version)
            trace = _request_json(client.get(f"{base_url}/api/v2/inspections/{task_id}/trace"))
            events = trace.get("events", [])
            if not isinstance(events, list):
                raise ValueError("Trace API response must contain an events list")
            trace_events = [
                _trace_event(task_id, event) for event in events if isinstance(event, dict)
            ]
            semantic_metadata.extend(_semantic_metadata(trace_events))
            case_results.append(
                _case_result(
                    case,
                    report,
                    trace_events,
                    latency_ms=int((perf_counter() - started_at) * 1000),
                )
            )
    finally:
        if owns_client:
            client.close()
    return _run_result(
        mode="live",
        dataset_version=dataset_version,
        versions={
            "dataset": dataset_version,
            "rule": ",".join(sorted(rule_versions)) or None,
            "prompt": _first_metadata_value(semantic_metadata, "prompt_version"),
            "model": _first_metadata_value(semantic_metadata, "model_name"),
            "embedding": settings.bge_embedding_model,
            "reranker": settings.bge_reranker_model,
            "threshold": None,
        },
        case_results=case_results,
    )


def write_result(
    result: EvaluationRunResult, output_dir: Path, *, now: datetime | None = None
) -> Path:
    """Write only normalized, privacy-safe evaluation data to a timestamped JSON file."""
    timestamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"evaluation-{result.mode}-{timestamp}.json"
    path.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def parse_cli_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI options while retaining ValueError semantics for invalid candidates."""
    parser = argparse.ArgumentParser(description="运行食品商品文案质检评测")
    parser.add_argument("--dataset")
    parser.add_argument("--rules")
    parser.add_argument("--output-dir", default="evaluation/results")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--api-base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--candidate", action="store_true")
    parser.add_argument("--baseline")
    arguments = parser.parse_args(argv)
    if arguments.candidate and not arguments.baseline:
        raise ValueError("candidate 评测必须提供 baseline 路径")
    if not arguments.dataset or not arguments.rules:
        raise ValueError("必须提供 --dataset 和 --rules")
    return arguments


def apply_baseline(
    result: EvaluationRunResult, baseline: EvaluationRunResult
) -> EvaluationRunResult:
    """Attach candidate-vs-baseline Diff after verifying dataset compatibility."""
    if result.dataset_version != baseline.dataset_version:
        raise ValueError("candidate 与 baseline 的 dataset_version 不一致")
    baseline_by_case_id = {case.case_id: case for case in baseline.case_results}
    case_results: list[EvaluationCaseResult] = []
    for candidate in result.case_results:
        previous = baseline_by_case_id.get(candidate.case_id)
        if previous is None:
            raise ValueError(f"baseline 缺少 case_id：{candidate.case_id}")
        case_results.append(
            candidate.model_copy(
                update={"baseline_diff": build_output_diff(baseline=previous, candidate=candidate)}
            )
        )
    return result.model_copy(update={"case_results": case_results})


def load_cases(path: Path) -> list[GoldenCase]:
    """Load owner-provided Golden Dataset JSON without deriving new labels."""
    payload = _load_json_list(path)
    cases = [GoldenCase.model_validate(item) for item in payload]
    _dataset_version(cases)
    return cases


def load_rules(path: Path) -> list[Rule]:
    """Load only project-provided Rule JSON through the frozen Rule Contract."""
    return [Rule.model_validate(item) for item in _load_json_list(path)]


def main(argv: Sequence[str] | None = None) -> Path:
    """Run the configured evaluation mode and return the generated result-file path."""
    arguments = parse_cli_arguments(argv)
    cases = load_cases(Path(arguments.dataset))
    rules = load_rules(Path(arguments.rules))
    if arguments.live:
        result = run_live(
            cases=cases,
            settings=Settings.from_environment(),
            api_base_url=arguments.api_base_url,
            http_client=None,
        )
    else:
        result = run_offline(cases=cases, rules=rules, now=datetime.now(UTC))
    if arguments.candidate:
        baseline = EvaluationRunResult.model_validate(
            json.loads(Path(arguments.baseline).read_text(encoding="utf-8"))
        )
        result = apply_baseline(result, baseline)
    return write_result(result, Path(arguments.output_dir))


def _case_result(
    case: GoldenCase,
    report: InspectionReport,
    traces: list[TraceEvent],
    *,
    latency_ms: int,
) -> EvaluationCaseResult:
    expected_issues = [
        NormalizedIssue(
            field=issue.field,
            rule_ids=sorted(issue.rule_ids),
            evidence_span=issue.evidence_span,
            risk_level=issue.risk_level,
        )
        for issue in case.expected_issues
    ]
    result = EvaluationCaseResult(
        case_id=case.case_id,
        task_status=report.status,
        expected_risk_level=case.expected_risk_level,
        observed_risk_level=report.automated_risk_level,
        expected_issues=expected_issues,
        observed_issues=[normalize_issue(issue) for issue in report.issues],
        expected_rule_ids=sorted(case.expected_rule_ids),
        observed_rule_ids=sorted(
            {rule_id for issue in report.issues for rule_id in issue.rule_ids}
        ),
        review_required=report.review_required,
        degradation_flags=report.degradation_flags,
        latency_ms=latency_ms,
        semantic_metadata=_semantic_metadata(traces),
        observed_evidence_grounded=[_evidence_grounded(case, issue) for issue in report.issues],
    )
    expected_result = result.model_copy(
        update={
            "observed_risk_level": case.expected_risk_level,
            "observed_issues": expected_issues,
            "observed_rule_ids": sorted(case.expected_rule_ids),
            "review_required": case.expected_risk_level is RiskLevel.HIGH,
        }
    )
    return result.model_copy(
        update={"expected_diff": build_output_diff(baseline=expected_result, candidate=result)}
    )


def _evidence_grounded(case: GoldenCase, issue: Issue) -> bool:
    field_value = _field_value(case, issue.field)
    if field_value is None:
        return False
    if issue.evidence_span in field_value:
        return True
    if issue.field.startswith("attributes."):
        return issue.evidence_span == issue.field.removeprefix("attributes.")
    return False


def _field_value(case: GoldenCase, field: str) -> str | None:
    product = case.input
    if field == "title":
        return product.title
    if field == "selling_points":
        return "\n".join(product.selling_points)
    if field == "description":
        return product.description
    if field == "marketing_description":
        return product.marketing_description
    if field.startswith("attributes."):
        value = getattr(product.attributes, field.removeprefix("attributes."), None)
        return value if isinstance(value, str) else None
    return None


def _run_result(
    *,
    mode: str,
    dataset_version: str,
    versions: dict[str, str | None],
    case_results: list[EvaluationCaseResult],
) -> EvaluationRunResult:
    failures = Counter(flag for result in case_results for flag in result.degradation_flags)
    return EvaluationRunResult(
        mode=mode,  # type: ignore[arg-type]
        dataset_version=dataset_version,
        versions=versions,
        metrics=compute_metrics(case_results),
        case_results=case_results,
        failure_summary=dict(sorted(failures.items())),
    )


def _dataset_version(cases: list[GoldenCase]) -> str:
    versions = {case.dataset_version for case in cases}
    if len(versions) != 1:
        raise ValueError("一次评测只能使用一个 dataset_version")
    if not versions:
        raise ValueError("评测数据集不能为空")
    return next(iter(versions))


def _rule_versions(rules: list[Rule]) -> str | None:
    versions = sorted({rule.version for rule in rules})
    return ",".join(versions) if versions else None


def _require_live_configuration(settings: Settings) -> None:
    required = {
        "BGE_API_BASE_URL": settings.bge_api_base_url,
        "BGE_API_KEY": settings.bge_api_key,
        "DEEPSEEK_API_KEY": settings.deepseek_api_key,
        "BGE_EMBEDDING_MODEL": settings.bge_embedding_model,
        "BGE_RERANKER_MODEL": settings.bge_reranker_model,
        "DEEPSEEK_MODEL": settings.deepseek_model,
    }
    for name, value in required.items():
        if not value.strip():
            raise ValueError(f"实时评测缺少 {name}")


def _request_json(response: httpx.Response) -> dict[str, object]:
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("API response must be an object")
    return payload


def _trace_event(task_id: str, event: dict[str, object]) -> TraceEvent:
    return TraceEvent.model_validate({"task_id": task_id, **event})


def _semantic_metadata(traces: list[TraceEvent]) -> list[dict[str, object]]:
    return [trace.metadata for trace in traces if trace.step_name == "semantic_risk_skill"]


def _first_metadata_value(metadata: list[dict[str, object]], key: str) -> str | None:
    for item in metadata:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _load_json_list(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError(f"JSON 文件必须是对象数组：{path}")
    return payload
