# Phase 2：食品同步质检 MVP 设计

## 目标

在不引入 LangGraph、LLM、RAG、Redis/Celery 或自动优化的前提下，交付食品类商品文本的同步质检闭环：接收商品输入、加载项目方提供的规则、执行确定性检查、生成可解释报告、持久化任务/结果/Trace，并通过最小 FastAPI 接口查询结果。

## 已确认决策

- 中国大陆电商文本质检场景；系统是辅助质检工具，不承担法律裁决或合规责任认定。
- 食品是 MVP 唯一完整实现类目；美妆与 3C 仅保留未来扩展边界。
- `data/rules/food_rules.json` 和 `evaluation/datasets/food_golden_dataset.json` 是项目方已确认的 v1.0 基线，可提交到 Git 并作为验收依据。
- SQLAlchemy 通过 PyMySQL 连接本地 Docker 中的 MySQL 8.0。
- 整体风险确定性聚合：任一 high Issue 为 high；否则取所有 Issue 的最高等级；无 Issue 为 pass。
- 首个业务 migration 只创建 `products`、`product_revisions`、`quality_rules`、`inspection_tasks`、`inspection_results`、`inspection_issues`、`agent_traces`。
- 优化必须显式触发；本阶段不实现优化。

## 范围与非目标

### 本阶段范围

```text
ProductInput
  -> 同步 Application Service
  -> RuleRepository + Food Tools
  -> Issue + 风险聚合
  -> InspectionReport + MySQL Trace
  -> FastAPI 查询接口
```

### 明确不做

- LangGraph 图、节点或 `InspectionState` 运行时编排。
- DeepSeek 调用、Prompt、语义判断、结构化模型输出和 Repair。
- Elasticsearch、BM25、向量检索、Hybrid Retrieval、Reranker。
- Redis、Celery、异步、重试、限流、批处理。
- 人审表、Review Task 或反馈闭环。
- Streamlit 页面和自动/显式文案优化实现。
- 标题长度检查：v1.0 规则和数据集未定义阈值。

## 模块设计

| 模块 | Phase 2 职责 |
| --- | --- |
| `contracts/` | Pydantic 公共输入、规则、Issue、ToolResult、报告与 Trace Contract |
| `db/` | SQLAlchemy ORM、Repository、Session、首个 Alembic migration |
| `scripts/` | 规则 JSON 导入与样例 JSON 校验/加载入口 |
| `tools/food/` | 文本表达命中、必填属性、规格一致性、风险聚合的确定性 Tool |
| `skills/food/` | FoodQualitySkill：组合 Food Tools 与规则，不调用 LLM |
| `app/services/` | 同步 InspectionApplicationService 与事务边界 |
| `app/api/` | 创建、状态查询、报告查询的最小 FastAPI 路由 |
| `observability/tracing/` | 最小结构化 Trace 持久化 |
| `tests/` | Contract、Tool、迁移、Repository、Service、API 与 Golden Dataset 回归 |

依赖只能向内：`app -> services -> skills/tools/repositories -> db/contracts`。Tools 不读取环境变量、不调用数据库、不调用 LLM。

## Contract 设计

### ProductInput 与 FoodAttributes

`ProductInput` 包含 `product_id`、`product_revision`、`category`、`title`、`selling_points`、`description`、`attributes`、`marketing_description` 与 `trigger_source`。

食品最小属性为 `ingredients`、`shelf_life`、`storage_method`、`origin`；`applicable_people`、`net_content`、`brand` 为可选扩展属性。Phase 2 仅接受 `category="食品"`。

### Rule

Rule JSON 维持 v1.0 的字段：`rule_id`、`version`、`category`、`field_scope`、`issue_type`、`risk_level`、`rule_strength`、`rule_text`、`bad_examples`、`rewrite_hint`、`status`、`effective_at`。

规则导入前必须经过 Pydantic 校验；运行时只使用 `enabled` 且类目为食品的规则。

### Issue、ToolResult 与 InspectionReport

每个 Issue 包含字段、问题类型、风险等级、`evidence_span`、`evidence`、`rule_ids`、来源、置信度和建议。确定性 Tools 的置信度固定为 1.0。`evidence_span` 必须定位在商品字段原文中；属性缺失使用属性键名作为证据定位。

ToolResult 统一包含 `name`、`status`、`issues`、`warnings`、`trace_refs`。InspectionReport 包含任务 ID、状态、自动风险、`review_required`、问题列表、降级标记和 Trace ID；本阶段不产生 `optimized_content`。

## 数据库设计

| 表 | 最小职责 |
| --- | --- |
| `products` | 商品稳定身份与类目 |
| `product_revisions` | 原始商品 JSON、修订号与内容哈希 |
| `quality_rules` | 已导入规则及版本、状态、生效时间、规则正文 |
| `inspection_tasks` | 任务状态、产品修订、规则版本、触发来源与错误摘要 |
| `inspection_results` | 自动风险等级、报告 JSON、复核标记与降级标记 |
| `inspection_issues` | 可检索的字段问题、证据、规则引用、来源和置信度 |
| `agent_traces` | 执行步骤、工具、规则、决策、状态、耗时和错误 |

数据库 Schema 只能经 Alembic migration 变更。Phase 2 不创建评测、人审、RAG 或 LLM 调用表。

## 规则和工具设计

### 文本表达检查

对 Rule 的 `bad_examples` 执行字段范围内的确定性文本匹配。命中时，使用规则自身的 `issue_type`、`risk_level`、`rewrite_hint` 与 `rule_id` 创建 Issue。此能力仅检测明确表达，不推断隐晦语义。

### 必填属性检查

固定映射如下，映射仅将现有食品属性与项目方提供的规则关联，不生成新业务规则：

```text
ingredients     -> food_attribute_005
shelf_life      -> food_attribute_006
storage_method  -> food_attribute_007
origin          -> food_attribute_008
```

空字符串、缺失字段或仅含空白均形成对应 low Issue。

### 规格一致性检查

仅当可从标题、详情或 `attributes.net_content` 中确定性提取相同单位的规格时比较。存在不同值时，按 `food_spec_009` 输出 medium Issue。无法确定或单位不可比较时不猜测、不输出 Issue。

### 风险聚合与复核标记

按已确认的最大等级规则产生整体自动风险。high 自动风险设置 `review_required=true` 与原因“命中 high 风险”；本阶段只保存该标记，不创建人工复核任务。

## 同步服务和 API

同步调用路径：

```text
POST /api/v2/inspections
  -> InspectionApplicationService
  -> 保存 product / revision / running task
  -> 读取 enabled 食品规则
  -> FoodQualitySkill
  -> 持久化 issues、result、trace
  -> success 或 failed task
```

最小接口：

| 接口 | 行为 |
| --- | --- |
| `POST /api/v2/inspections` | 同步执行审核并返回 `task_id`、状态与结果查询地址 |
| `GET /api/v2/inspections/{task_id}` | 返回任务状态和基本元数据 |
| `GET /api/v2/inspections/{task_id}/result` | 返回完整 InspectionReport |

输入 Contract 失败或非食品类目返回 422；任务不存在返回 404；规则加载或持久化失败时任务标记为 failed，记录最小 Trace，且 API 不返回伪成功。

## 数据与测试

- 将 Golden Dataset 的 `notes` 更新为“项目方已确认的 v1.0 基线”。
- 为两份 JSON 保留结构、交叉引用和证据可定位测试。
- 为每个 Tool 添加单测：明确文本命中、属性缺失、规格冲突、无问题输入和风险聚合。
- 使用独立 MySQL 测试数据库执行 migration、Repository、Service 与 API 集成测试，避免污染本地开发库。
- 以 10 条 Golden Dataset 执行端到端同步回归，逐项验证 Issue、Rule ID 和总体风险。

## 完成标准

1. `PyMySQL` 已锁定，MySQL 连接由配置集中管理。
2. 两份 v1.0 JSON 数据及其说明已提交。
3. 首个 migration 能在空 MySQL 上创建 7 张最小表。
4. 规则 JSON 可导入并记录版本。
5. 同步 FoodQualitySkill 能生成可定位、可引用的 Issue 和确定性风险等级。
6. 三个最小 FastAPI 接口可创建并查询审核任务。
7. 每个任务持久化结果、Issue 与最小 Trace。
8. 10 条 Golden Dataset 回归通过，pytest、ruff 与 MySQL 集成测试通过。
9. 不包含 LangGraph、LLM、RAG、Redis/Celery、自动优化或人审实现。
