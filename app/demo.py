from __future__ import annotations

import json
import os
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import httpx
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
WritableCopyField = Literal[
    "title",
    "selling_points",
    "description",
    "marketing_description",
]
WRITABLE_FIELDS: tuple[WritableCopyField, ...] = (
    "title",
    "selling_points",
    "description",
    "marketing_description",
)


class DemoApiError(RuntimeError):
    """A user-readable failure returned by the FastAPI boundary."""


class DemoApiClient:
    """The Demo's only gateway to inspection, evidence, trace, and optimization data."""

    def __init__(self, *, http_client: httpx.Client, base_url: str) -> None:
        self._http_client = http_client
        self._base_url = base_url.rstrip("/")

    def create_inspection(
        self, product: Mapping[str, object], *, semantic_enabled: bool
    ) -> dict[str, object]:
        return self._request_json(
            self._http_client.post(
                f"{self._base_url}/api/v2/inspections",
                json=dict(product),
                headers={"X-Semantic-Inspection": "enabled" if semantic_enabled else "disabled"},
            )
        )

    def fetch_task(self, task_id: str) -> dict[str, object]:
        return self._request_json(self._http_client.get(self._url(task_id)))

    def fetch_result(self, task_id: str) -> dict[str, object]:
        return self._request_json(self._http_client.get(f"{self._url(task_id)}/result"))

    def fetch_trace(self, task_id: str) -> dict[str, object]:
        return self._request_json(self._http_client.get(f"{self._url(task_id)}/trace"))

    def fetch_rule_evidence(self, task_id: str) -> dict[str, object]:
        return self._request_json(self._http_client.get(f"{self._url(task_id)}/rule-evidence"))

    def optimize(self, task_id: str, fields: list[WritableCopyField]) -> dict[str, object]:
        return self._request_json(
            self._http_client.post(f"{self._url(task_id)}/optimization", json={"fields": fields})
        )

    def _url(self, task_id: str) -> str:
        return f"{self._base_url}/api/v2/inspections/{task_id}"

    @staticmethod
    def _request_json(response: httpx.Response) -> dict[str, object]:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            detail = _error_detail(error.response)
            message = f"API 请求失败（HTTP {error.response.status_code}）：{detail}"
            raise DemoApiError(message) from error
        except httpx.HTTPError as error:
            raise DemoApiError(f"无法连接 FastAPI：{error}") from error

        payload = response.json()
        if not isinstance(payload, dict):
            raise DemoApiError("API 返回格式异常：应为 JSON 对象")
        return payload


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return "服务未返回可读错误信息"
    if isinstance(payload, Mapping) and isinstance(payload.get("detail"), str):
        return payload["detail"]
    return "服务未返回可读错误信息"


def _load_samples() -> dict[Literal["pass", "medium", "high"], dict[str, object]]:
    path = ROOT / "evaluation/datasets/food_golden_dataset.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Golden Dataset 必须是对象数组")
    samples: dict[Literal["pass", "medium", "high"], dict[str, object]] = {}
    for case in payload:
        if not isinstance(case, dict):
            continue
        risk = case.get("expected_risk_level")
        product = case.get("input")
        if risk in {"pass", "medium", "high"} and isinstance(product, dict):
            samples.setdefault(risk, product)
    missing = {"pass", "medium", "high"} - samples.keys()
    if missing:
        raise ValueError(f"Golden Dataset 缺少 Demo 样例：{', '.join(sorted(missing))}")
    return samples


def _demo_client() -> DemoApiClient:
    return DemoApiClient(
        http_client=httpx.Client(timeout=30.0),
        base_url=os.environ.get("STREAMLIT_API_BASE_URL", DEFAULT_API_BASE_URL),
    )


def _poll_report(client: DemoApiClient, task_id: str) -> dict[str, object]:
    for attempt in range(3):
        task = client.fetch_task(task_id)
        if task.get("status") in {"success", "failed"}:
            return client.fetch_result(task_id)
        if attempt < 2:
            time.sleep(0.2)
    raise DemoApiError("质检任务仍在执行，请稍后重试")


def _writable_issue_fields(report: Mapping[str, object]) -> list[WritableCopyField]:
    issues = report.get("issues")
    if not isinstance(issues, list):
        return []
    fields = {
        issue.get("field")
        for issue in issues
        if isinstance(issue, Mapping) and issue.get("field") in WRITABLE_FIELDS
    }
    return [field for field in WRITABLE_FIELDS if field in fields]


def _render_report(report: Mapping[str, object]) -> None:
    st.subheader("质检结果")
    left, middle, right = st.columns(3)
    left.metric("自动风险等级", str(report.get("automated_risk_level", "未知")))
    middle.metric("是否需要人工复核", "是" if report.get("review_required") else "否")
    right.metric("任务状态", str(report.get("status", "未知")))

    review_reasons = report.get("review_reasons", [])
    if review_reasons:
        st.warning("人工复核原因：" + "；".join(map(str, review_reasons)))
    flags = report.get("degradation_flags", [])
    if flags:
        st.info("降级标记：" + "；".join(map(str, flags)))

    issues = report.get("issues", [])
    if not issues:
        st.success("未发现需要展示的风险问题。")
        return
    for index, issue in enumerate(issues, start=1):
        if not isinstance(issue, Mapping):
            continue
        st.markdown(f"#### Issue {index} · {issue.get('risk_level', '未知')}")
        st.write(f"字段：`{issue.get('field', '')}`")
        st.write(f"证据：{issue.get('evidence_span', '')}")
        st.write(f"规则 ID：{', '.join(map(str, issue.get('rule_ids', [])))}")
        st.write(f"修改建议：{issue.get('suggestion', '')}")


def _render_rule_evidence(evidence: Mapping[str, object]) -> None:
    st.subheader("规则依据")
    rules = evidence.get("rules", [])
    if not rules:
        st.caption("该报告没有命中的规则依据。")
        return
    for rule in rules:
        if not isinstance(rule, Mapping):
            continue
        with st.expander(f"{rule.get('rule_id', '')} · v{rule.get('version', '')}"):
            st.write(rule.get("rule_text", ""))
            st.write("适用字段：" + "、".join(map(str, rule.get("field_scope", []))))
            st.write("改写提示：" + str(rule.get("rewrite_hint", "")))


def _render_trace(trace: Mapping[str, object]) -> None:
    st.subheader("安全 Trace")
    events = trace.get("events", [])
    if not events:
        st.caption("该任务没有可展示的 Trace 事件。")
        return
    for event in events:
        if not isinstance(event, Mapping):
            continue
        title = (
            f"{event.get('step_name', '')} · {event.get('status', '')} "
            f"· {event.get('latency_ms', 0)} ms"
        )
        with st.expander(title):
            st.json(dict(event))


def _render_optimization(client: DemoApiClient, task_id: str, report: Mapping[str, object]) -> None:
    st.subheader("显式文案优化")
    fields = _writable_issue_fields(report)
    selected = st.multiselect("选择要优化的命中字段", fields, disabled=not fields)
    if not fields:
        st.caption("当前报告没有可优化的命中文案字段。")
        return
    if st.button("请求优化", disabled=not selected):
        try:
            st.session_state["optimization_result"] = client.optimize(task_id, selected)
        except DemoApiError as error:
            st.error(str(error))
            return

    result = st.session_state.get("optimization_result")
    if isinstance(result, Mapping) and result.get("source_task_id") == task_id:
        status = str(result.get("status", "未知"))
        if status == "success":
            st.success("优化已完成并通过二次质检。")
        else:
            st.warning(f"优化结果：{status}")
        st.json(dict(result))


def run() -> None:
    st.set_page_config(page_title="食品商品文案质检 Demo", layout="wide")
    st.title("食品商品文案质检与优化 Demo")
    st.caption("Demo 仅通过 FastAPI 调用系统能力；人工复核工作台未在 MVP 实现。")
    st.info("语义质检默认关闭。启用后会发起 BGE 与 DeepSeek 调用，并产生相应成本。")

    try:
        samples = _load_samples()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        st.error(f"无法读取本地 Golden Dataset Demo 样例：{error}")
        return

    sample_name = st.selectbox(
        "加载项目方 Golden Dataset 样例",
        options=["pass", "medium", "high"],
        format_func=lambda value: {
            "pass": "通过样例",
            "medium": "中风险样例",
            "high": "高风险样例",
        }[value],
    )
    sample = samples[sample_name]
    attributes = sample["attributes"]
    if not isinstance(attributes, Mapping):
        st.error("样例 attributes 格式异常")
        return

    with st.form("inspection-form"):
        title = st.text_input("商品标题", value=str(sample["title"]))
        selling_points = st.text_area(
            "商品卖点（每行一条）", value="\n".join(map(str, sample["selling_points"]))
        )
        description = st.text_area("商品详情", value=str(sample["description"]), height=120)
        marketing_description = st.text_area(
            "营销描述", value=str(sample["marketing_description"]), height=100
        )
        st.markdown("##### 食品必填属性")
        ingredients = st.text_input("配料", value=str(attributes["ingredients"]))
        shelf_life = st.text_input("保质期", value=str(attributes["shelf_life"]))
        storage_method = st.text_input("贮存方式", value=str(attributes["storage_method"]))
        origin = st.text_input("产地", value=str(attributes["origin"]))
        semantic_enabled = st.checkbox("启用语义质检（会调用远程模型）", value=False)
        submitted = st.form_submit_button("开始质检")

    if submitted:
        product: dict[str, object] = {
            "product_id": str(sample["product_id"]),
            "product_revision": int(sample["product_revision"]),
            "category": "食品",
            "title": title,
            "selling_points": [item for item in selling_points.splitlines() if item.strip()],
            "description": description,
            "attributes": {
                "ingredients": ingredients,
                "shelf_life": shelf_life,
                "storage_method": storage_method,
                "origin": origin,
            },
            "marketing_description": marketing_description,
            "trigger_source": "streamlit_demo",
        }
        try:
            client = _demo_client()
            created = client.create_inspection(product, semantic_enabled=semantic_enabled)
            task_id = str(created["task_id"])
            report = _poll_report(client, task_id)
            st.session_state.update(
                {"task_id": task_id, "report": report, "optimization_result": None}
            )
        except (DemoApiError, KeyError, ValueError) as error:
            st.error(f"质检未完成：{error}")

    task_id = st.session_state.get("task_id")
    report = st.session_state.get("report")
    if not isinstance(task_id, str) or not isinstance(report, Mapping):
        return

    _render_report(report)
    try:
        client = _demo_client()
        _render_rule_evidence(client.fetch_rule_evidence(task_id))
        _render_trace(client.fetch_trace(task_id))
        _render_optimization(client, task_id, report)
    except DemoApiError as error:
        st.error(str(error))


if __name__ == "__main__":
    run()
