# Phase 2 同步质检 API

当前仅支持食品类商品的同步质检。固定 LangGraph 工作流会先执行全部确定性检查；只有请求显式开启时，才会继续执行受控的规则检索与语义判断。Redis、Celery、异步队列和自动文案优化尚未实现；文案优化仅可由用户显式请求。

## 启动

```bash
docker compose up -d mysql elasticsearch
uv run alembic upgrade head
uv run python scripts/import_rules.py data/rules/food_rules.json
uv run python scripts/sync_rules_to_es.py
set -a
source .env
set +a
uv run uvicorn app.main:app --reload
```

服务默认监听 `http://127.0.0.1:8000`，交互式文档位于 `/docs`。

## 创建质检任务

`POST /api/v2/inspections`

```json
{
  "product_id": "demo_food_002",
  "product_revision": 1,
  "category": "食品",
  "title": "草本风味袋泡茶 30g",
  "selling_points": ["草本配方"],
  "description": "本产品可有效治疗失眠，睡前冲泡即可。",
  "attributes": {
    "ingredients": "决明子、菊花",
    "shelf_life": "12个月",
    "storage_method": "阴凉干燥处保存",
    "origin": "安徽省亳州市"
  },
  "marketing_description": "袋泡茶 10 袋装。",
  "trigger_source": "api"
}
```

成功时返回 `201`：

```json
{
  "task_id": "<uuid>",
  "status": "success",
  "result_url": "/api/v2/inspections/<uuid>/result"
}
```

非食品类目或不满足 `ProductInput` Contract 的请求返回 `422`。执行失败返回通用 `500`，不会暴露内部异常详情。

默认不执行语义质检；如需启用，传入下列请求头：

```text
X-Semantic-Inspection: enabled
```

该请求头仅接受 `enabled` 或 `disabled`，缺省值为 `disabled`。

## 查询任务和报告

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| `GET` | `/api/v2/inspections/{task_id}` | 返回任务状态、触发来源和实际使用的规则版本。 |
| `GET` | `/api/v2/inspections/{task_id}/result` | 返回完整 `InspectionReport`，包括风险、Issue、复核标记和 Trace ID。 |
| `GET` | `/api/v2/inspections/{task_id}/trace` | 返回脱敏后的 Tool/Skill 执行摘要和安全调用元数据。 |
| `GET` | `/api/v2/inspections/{task_id}/rule-evidence` | 返回该报告 Issue 所引用的、任务执行时实际加载的规则版本。 |
| `POST` | `/api/v2/inspections/{task_id}/optimization` | 对指定存在风险的文案字段执行一次显式优化和二次质检。 |

未知任务或尚无报告时返回 `404`。

## 查询规则依据

`GET /api/v2/inspections/{task_id}/rule-evidence` 只返回当前报告中 Issue 所引用的规则；响应按 `(rule_id, version)` 排序：

```json
{
  "task_id": "<uuid>",
  "rules": [
    {
      "rule_id": "food_health_002",
      "version": "1.0.0",
      "field_scope": ["description"],
      "risk_level": "medium",
      "rule_text": "普通食品文案应避免未经依据支撑的保健或身体功能改善暗示。",
      "rewrite_hint": "删除功能改善暗示，改为描述原料、口感或冲泡方式。"
    }
  ]
}
```

系统按任务完成时记录的 `(rule_id, version)` 精确查询，即使当前规则已被禁用或已导入新版本，也不会替换历史任务的依据。通过的报告返回空 `rules` 数组。该接口不返回商品原文、规则无关字段或当前启用状态。

## 显式文案优化

`POST /api/v2/inspections/{task_id}/optimization` 只接受允许改写的文案字段；`attributes` 不可改写：

```json
{
  "fields": ["description"]
}
```

请求必须指向成功完成的质检任务，且所选字段必须存在 Issue。系统读取该任务绑定的历史规则和原始商品修订，生成最小改动候选文案后在内存中执行二次质检；不会修改源商品修订、源任务或源报告，也不会自动发布文案。

生成结果只允许请求字段，必须保留原始标题/详情中的规格标识，且不得新增与已知配料、保质期、储存方式或产地冲突的显式表述。模型输出不合规时最多请求一次结构化修复；首次二次质检失败后最多再生成一版包含失败原因的候选文案。

成功或已尝试但未通过的请求均返回 `200` 和 `OptimizationResult`：

| `status` | 含义 |
| --- | --- |
| `success` | 候选文案通过二次质检。 |
| `verification_failed` | 二次质检仍存在风险、降级或需要人工复核。 |
| `failed` | 模型调用或受控输出校验失败。 |

未知源任务返回 `404`；任务未成功或所选字段无 Issue 返回 `409`；字段为空、重复、包含 `attributes` 或其他非法 body 返回 `422`。优化 Trace 仅保存 Provider、Prompt/模型版本、Token、耗时、修复状态、步骤、尝试次数和错误类别，不保存完整 Prompt、原文或模型原始输出。
