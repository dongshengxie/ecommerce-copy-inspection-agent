# Phase 3 Controlled LangGraph Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Phase 2 synchronous service's linear in-memory orchestration with a fixed, deterministic LangGraph workflow while preserving the food MVP's API and Golden Dataset behavior.

**Architecture:** `InspectionApplicationService` continues to own task lifecycle, SQLAlchemy sessions, persistence, and failure handling. It supplies a `RuleLoader` callback to `FoodInspectionWorkflow`; the compiled `StateGraph` then runs exactly four nodes—`load_rules`, `food_quality_skill`, `risk_aggregator`, and `report_builder`—and returns a report, rule version, and node Trace events for the service to persist.

**Tech Stack:** Python 3.12, LangGraph (already locked), Pydantic, SQLAlchemy 2.x, MySQL 8.0, pytest, ruff.

## Global Constraints

- Food remains the only supported category.
- The graph is a controlled fixed workflow; do not add ReAct, dynamic tool selection, model-directed routing, or conditional business branches.
- Do not add or modify public Pydantic Contracts, Rule JSON, Golden Dataset, database tables, Alembic migrations, API routes, or API response shapes.
- Do not add LLM, Prompt, RAG, Elasticsearch, Redis, Celery, optimization, human-review, retry, timeout, or rate-limit behavior.
- Nodes do not access SQLAlchemy, MySQL, environment variables, or LLM providers; the injected `RuleLoader` is their only rule source.
- Every graph node appends one `TraceEvent`; node failures propagate to the existing service failure transaction.
- Existing ten-case Golden Dataset results must remain identical.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `agent/state/inspection.py` | Internal TypedDict state, `RuleLoader` protocol alias, and internal `WorkflowResult`. |
| `agent/graph/food_inspection_workflow.py` | Compiled four-node LangGraph and deterministic node implementations. |
| `app/services/inspection.py` | Creates the workflow with a session-scoped loader and persists its returned report and traces. |
| `tests/agent/test_food_inspection_workflow.py` | Pure workflow unit tests using a fake loader and existing food rules. |
| `tests/integration/test_inspection_service.py` | Confirms service persists all four graph node Trace records. |
| `tests/evaluation/test_food_sync_regression.py` | Retained full regression proving graph integration preserves baseline. |
| `README.md` | Describes Phase 3's controlled LangGraph status and exclusions. |

### Task 1: Add an internal state and pure controlled workflow

**Files:**
- Create: `agent/state/inspection.py`
- Create: `agent/graph/food_inspection_workflow.py`
- Create: `tests/agent/test_food_inspection_workflow.py`

**Interfaces:**
- Consumes: `ProductInput`, `Rule`, `SkillResult`, `RiskLevel`, `InspectionReport`, `TaskStatus`, `TraceEvent`, `FoodQualitySkill.inspect(product, rules)`, and `aggregate_risk(issues)`.
- Produces: `RuleLoader = Callable[[], list[Rule]]`, `WorkflowResult(report: InspectionReport, rule_version: str, trace_events: list[TraceEvent])`, and `FoodInspectionWorkflow(rule_loader, food_quality_skill).invoke(task_id, product)`.

- [ ] **Step 1: Write the failing workflow tests**

```python
def test_workflow_returns_case_001_pass_with_fixed_node_traces() -> None:
    result = FoodInspectionWorkflow(_load_rules, FoodQualitySkill()).invoke(
        task_id="task-001", product=_case_input("food_case_001")
    )

    assert result.report.automated_risk_level is RiskLevel.PASS
    assert [trace.step_name for trace in result.trace_events] == [
        "load_rules",
        "food_quality_skill",
        "risk_aggregator",
        "report_builder",
    ]


def test_workflow_returns_case_004_high_and_review_required() -> None:
    result = FoodInspectionWorkflow(_load_rules, FoodQualitySkill()).invoke(
        task_id="task-004", product=_case_input("food_case_004")
    )

    assert len(result.report.issues) == 6
    assert result.report.automated_risk_level is RiskLevel.HIGH
    assert result.report.review_required is True


def test_workflow_propagates_rule_loader_failure() -> None:
    def failing_loader() -> list[Rule]:
        raise RuntimeError("rule store unavailable")

    with pytest.raises(RuntimeError, match="rule store unavailable"):
        FoodInspectionWorkflow(failing_loader, FoodQualitySkill()).invoke(
            task_id="task-failure", product=_case_input("food_case_001")
        )
```

- [ ] **Step 2: Run the focused tests to verify the missing-module failure**

Run: `uv run pytest tests/agent/test_food_inspection_workflow.py -q`

Expected: collection fails because `agent.graph.food_inspection_workflow` does not exist.

- [ ] **Step 3: Define the internal state and result types**

Create `agent/state/inspection.py` with an internal `InspectionState(TypedDict, total=False)`. Use `Annotated[list[TraceEvent], operator.add]` for `trace_events`, so every LangGraph node returns exactly one new trace without overwriting earlier traces. Define:

```python
RuleLoader = Callable[[], list[Rule]]


@dataclass(frozen=True)
class WorkflowResult:
    report: InspectionReport
    rule_version: str
    trace_events: list[TraceEvent]
```

The state contains `task_id`, `product`, `rules`, `skill_result`, `automated_risk_level`, `review_required`, `review_reasons`, `report`, and `trace_events`. Do not place Repository, Session, database URL, API, prompt, or model fields in the state.

- [ ] **Step 4: Implement the compiled four-node graph**

Create `FoodInspectionWorkflow` in `agent/graph/food_inspection_workflow.py`. In its constructor, save the injected `RuleLoader` and `FoodQualitySkill`, build a `StateGraph(InspectionState)`, add all four named nodes, add only these edges, and compile it:

```python
graph.add_edge(START, "load_rules")
graph.add_edge("load_rules", "food_quality_skill")
graph.add_edge("food_quality_skill", "risk_aggregator")
graph.add_edge("risk_aggregator", "report_builder")
graph.add_edge("report_builder", END)
```

Each node records elapsed milliseconds using `perf_counter()` and returns its state update plus a one-item `trace_events` list. Use the following node decisions:

| Node | Decision string |
| --- | --- |
| `load_rules` | `加载 {len(rules)} 条已启用食品规则` |
| `food_quality_skill` | `生成 {len(skill_result.issues)} 个确定性 Issue` |
| `risk_aggregator` | `自动风险等级为 {automated_risk_level.value}` |
| `report_builder` | `生成同步质检报告` |

`load_rules` derives `rule_version` only in `invoke()` after the graph returns, using `",".join(sorted({rule.version for rule in state["rules"]}))`. `risk_aggregator` sets `review_required` only when the risk is `RiskLevel.HIGH`, with `review_reasons=["命中 high 风险"]` in that case. `report_builder` creates the unchanged `InspectionReport` with `status=TaskStatus.SUCCESS`, `trace_id=task_id`, accumulated Issues, review fields, and no degradation flags.

- [ ] **Step 5: Run focused unit tests and formatting**

Run:

```bash
uv run pytest tests/agent/test_food_inspection_workflow.py -q
uv run ruff check agent tests/agent
uv run ruff format --check agent tests/agent
```

Expected: three tests pass and all graph node traces appear in fixed order.

- [ ] **Step 6: Commit the isolated workflow unit**

```bash
git add agent/state/inspection.py agent/graph/food_inspection_workflow.py tests/agent/test_food_inspection_workflow.py
git commit -m "feat: 添加受控食品质检工作流"
```

### Task 2: Make the application service delegate in-memory orchestration to LangGraph

**Files:**
- Modify: `app/services/inspection.py`
- Modify: `tests/integration/test_inspection_service.py`

**Interfaces:**
- Consumes: `FoodInspectionWorkflow.invoke(task_id=..., product=...) -> WorkflowResult` and `RuleRepository(session).list_enabled_food_rules`.
- Produces: persisted reports, Issue rows, and four success Trace records through existing `InspectionRepository.complete_task`.

- [ ] **Step 1: Extend the failing service integration assertion**

Replace the old two-step Trace expectation with a set comparison that avoids MySQL row-order assumptions:

```python
assert {trace.step_name for trace in session.scalars(select(AgentTraceModel)).all()} == {
    "load_rules",
    "food_quality_skill",
    "risk_aggregator",
    "report_builder",
}
```

- [ ] **Step 2: Run the service test to verify the old two-trace implementation fails**

Run: `MYSQL_PORT=3307 uv run pytest tests/integration/test_inspection_service.py -q`

Expected: failure because persisted Trace names are only `food_quality_skill` and `risk_aggregator`.

- [ ] **Step 3: Replace only the linear in-memory portion of `_complete_inspection`**

Remove direct use of `perf_counter`, `RuleRepository.list_enabled_food_rules`, `FoodQualitySkill.inspect`, `aggregate_risk`, and inline report/Trace construction from `_complete_inspection`. Keep `create_inspection` and `_record_failure` lifecycle behavior unchanged.

Inside the existing session context, instantiate and invoke the workflow with the repository method as its callback:

```python
workflow = FoodInspectionWorkflow(
    rule_loader=RuleRepository(session).list_enabled_food_rules,
    food_quality_skill=self._food_quality_skill,
)
result = workflow.invoke(task_id=task_id, product=product)
InspectionRepository(session).complete_task(
    task_id,
    result.report,
    result.rule_version,
    result.trace_events,
)
session.commit()
return result.report
```

Do not move database writes into graph nodes. Any workflow exception must still reach `create_inspection` and trigger the existing `_record_failure` transaction.

- [ ] **Step 4: Run the service test and existing API integration tests**

Run:

```bash
MYSQL_PORT=3307 uv run pytest tests/integration/test_inspection_service.py -q
MYSQL_PORT=3307 uv run pytest tests/integration/test_inspection_api.py -q
```

Expected: service persists four success traces; all three API behaviors remain unchanged.

- [ ] **Step 5: Commit the service integration**

```bash
git add app/services/inspection.py tests/integration/test_inspection_service.py
git commit -m "refactor: 使用 LangGraph 编排食品质检"
```

### Task 3: Prove behavior preservation and update operating documentation

**Files:**
- Modify: `README.md`
- Verify: `tests/evaluation/test_food_sync_regression.py`
- Verify: `tests/contract/test_models.py`, `tests/integration/test_inspection_api.py`, `tests/integration/test_rule_import.py`, `tests/integration/test_migration.py`

**Interfaces:**
- Consumes: the unchanged synchronous API and the owner-confirmed `evaluation/datasets/food_golden_dataset.json`.
- Produces: documented Phase 3 orchestration status and evidence that no Phase 2 behavior regressed.

- [ ] **Step 1: Update README's current-state sentence**

Replace the Phase 2 status sentence with one that states the MVP now has a controlled LangGraph workflow for the deterministic food inspection path. Explicitly retain the exclusions: LLM, RAG, Redis/Celery, human review, Streamlit, and copy optimization are not implemented.

- [ ] **Step 2: Run the full Golden Dataset regression**

Run: `MYSQL_PORT=3307 uv run pytest tests/evaluation/test_food_sync_regression.py -q`

Expected: all ten owner-confirmed cases pass with unchanged risk, normalized Issue, evidence span, and Rule ID assertions.

- [ ] **Step 3: Run final Phase 3 verification**

Run:

```bash
MYSQL_PORT=3307 uv run pytest -q
uv run ruff check .
uv run ruff format --check .
docker compose config -q
git diff --check
```

Expected: all tests pass, lint and formatting report no violations, Docker Compose validates, and no whitespace errors exist.

- [ ] **Step 4: Commit documentation and regression evidence**

```bash
git add README.md
git commit -m "docs: 说明受控 LangGraph 工作流"
```

## Plan Self-Review

- Spec coverage: Task 1 implements the fixed graph, internal state, injected loader, node Trace, pass/high behavior, and loader failure. Task 2 preserves service lifecycle and persistence. Task 3 proves API and Golden behavior and updates operating documentation.
- Scope: no task changes public Contract, schema, API shape, rules, dataset, or unapproved infrastructure.
- Type consistency: `FoodInspectionWorkflow.invoke` returns the `WorkflowResult` consumed by the existing service; `InspectionRepository.complete_task` continues to accept `InspectionReport`, rule version, and `list[TraceEvent]`.
- No placeholders: all task steps name exact files, interfaces, commands, assertions, expected outcomes, and commit boundaries.
