# Phase 3：受控 LangGraph 工作流设计

## 目标

在不改变 Phase 2 食品同步质检业务结果的前提下，用 LangGraph 替换应用服务内部的线性编排。工作流仅组合已存在的确定性规则查询、FoodQualitySkill 与风险聚合能力，为后续 RAG 和 LLM 节点预留受控扩展边界。

## 已确认范围

- 工作流只处理食品类同步质检。
- 固定节点顺序为 `load_rules`、`food_quality_skill`、`risk_aggregator`、`report_builder`。
- 本阶段不实现 LLM、Prompt、RAG、Elasticsearch、Redis、Celery、文案优化或人工复核任务。
- 不新增数据库表或 Alembic migration。
- 现有 `POST /api/v2/inspections` 与两个查询接口保持兼容。
- Golden Dataset 的 10 条输入、Issue、Rule ID、风险等级和复核标记保持不变。

## 方案选择

采用“Graph 只负责确定性编排，Application Service 负责生命周期与持久化”的方案。

```text
InspectionApplicationService
  -> 创建 product revision 和 running task
  -> FoodInspectionWorkflow.invoke
       -> load_rules
       -> food_quality_skill
       -> risk_aggregator
       -> report_builder
  -> 持久化 report / issues / traces
  -> success；失败时标记 failed 并保存 failure trace
```

Graph 不直接访问 Repository 或 MySQL。这样任务失败事务、数据库生命周期和 API 错误边界继续由现有应用服务统一管理，节点可作为纯确定性函数独立测试。

## 状态与节点

在 `agent/state/inspection.py` 内定义内部使用的 `InspectionState` TypedDict；在 `agent/graph/food_inspection_workflow.py` 内定义工作流。`InspectionState` 是固定工作流状态，不对 API 暴露，字段如下：

| 字段 | 写入节点 | 用途 |
| --- | --- | --- |
| `task_id` | 初始化 | 关联节点 Trace 与最终报告。 |
| `product` | 初始化 | 已校验的 `ProductInput`。 |
| `rules` | `load_rules` | 已启用食品 `Rule` 列表。 |
| `skill_result` | `food_quality_skill` | `FoodQualitySkill` 的确定性 Issue 输出。 |
| `automated_risk_level` | `risk_aggregator` | 最大风险聚合结果。 |
| `review_required` | `risk_aggregator` | 仅在 high 风险时为 true。 |
| `review_reasons` | `risk_aggregator` | high 风险时记录“命中 high 风险”。 |
| `report` | `report_builder` | 最终 `InspectionReport`。 |
| `trace_events` | 每个节点 | 节点级 `TraceEvent` 列表。 |

节点职责：

1. `load_rules` 通过调用方提供的 `RuleLoader` 读取已启用食品规则，记录规则数量与版本依据 Trace。
2. `food_quality_skill` 调用既有 `FoodQualitySkill.inspect(product, rules)`，不访问数据库、环境变量或 LLM。
3. `risk_aggregator` 调用既有 `aggregate_risk`，生成 high 风险复核标记与 Trace。
4. `report_builder` 根据状态创建 `InspectionReport`，不持久化。

所有边均为固定边；不采用 ReAct、动态工具选择或模型驱动跳转。节点异常交由应用服务捕获，沿用现有 `failed` 任务和 failure Trace 行为。

## 接口与依赖方向

新增 `FoodInspectionWorkflow`，构造时接收 `RuleLoader` 和 `FoodQualitySkill`，暴露：

```python
def invoke(self, *, task_id: str, product: ProductInput) -> WorkflowResult: ...
```

`WorkflowResult` 为内部结果对象，包含最终 `InspectionReport`、规则版本和节点 Trace。它不替代或修改已冻结的 `InspectionReport`、`SkillResult`、`Issue`、`TraceEvent` 等公共 Contract。

依赖方向保持为：

```text
app/services -> agent -> skills/tools
app/services -> db/repositories
```

调用方通过 `RuleLoader` 注入规则读取函数，避免 `agent/` 直接依赖 SQLAlchemy Repository。

## 测试与验收

- Workflow 单测覆盖无 Issue 的 pass、高风险 case 004、节点 Trace 顺序和 RuleLoader 失败传播。
- 应用服务集成测试验证 Graph 结果仍会保存任务、报告、Issue 和 Trace。
- 现有 API 集成测试和 10 条 Golden Dataset 回归必须继续通过。
- 测试断言节点 Trace 至少包含 `load_rules`、`food_quality_skill`、`risk_aggregator` 与 `report_builder`。
- 无新增依赖；使用 Phase 1 已锁定的 `langgraph`。

## 明确非目标

- 不实现 `InspectionState` 的 RAG、模型、优化、人工复核或异步字段。
- 不修改 Rule JSON、Golden Dataset 或公共 Pydantic Contract。
- 不增加条件分支、重试、超时、限流或队列逻辑。
