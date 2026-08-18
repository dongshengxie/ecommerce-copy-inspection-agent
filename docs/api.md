# Phase 2 同步质检 API

当前仅支持食品类商品的同步质检。固定 LangGraph 工作流会先执行全部确定性检查；只有请求显式开启时，才会继续执行受控的规则检索与语义判断。Redis、Celery、异步队列和自动文案优化尚未实现。

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
