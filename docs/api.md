# Phase 2 同步质检 API

本阶段仅支持食品类商品的同步确定性质检。接口不调用 LLM、RAG、LangGraph、Redis 或 Celery。

## 启动

```bash
docker compose up -d mysql
uv run alembic upgrade head
uv run python scripts/import_rules.py data/rules/food_rules.json
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

## 查询任务和报告

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| `GET` | `/api/v2/inspections/{task_id}` | 返回任务状态、触发来源和实际使用的规则版本。 |
| `GET` | `/api/v2/inspections/{task_id}/result` | 返回完整 `InspectionReport`，包括风险、Issue、复核标记和 Trace ID。 |

未知任务或尚无报告时返回 `404`。
