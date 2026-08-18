# 食品规则检索

## 数据归属

MySQL 的 `quality_rules` 是规则唯一事实来源。Elasticsearch 的 `food_rules_v1` 是可重建的检索投影，绝不作为规则写入目标，也不直接决定正式 Issue。

投影仅包含规则 ID、版本、类目、状态、适用字段、问题类型、风险等级、规则强度、规则检索文本和 1024 维向量；不包含商品原文、Prompt 或 LLM 原始输出。

## 本地同步与重建

在宿主机启动服务并加载规则后执行：

```bash
docker compose up -d mysql elasticsearch
uv run alembic upgrade head
uv run python scripts/import_rules.py data/rules/food_rules.json
uv run python scripts/sync_rules_to_es.py
```

同步命令只读取 MySQL 的已启用食品规则，按 `rule_id:version` 幂等写入 ES。需要重建时，删除 `food_rules_v1` 后重新运行同步命令即可；不会修改 MySQL。

## 检索流程

对同一份商品查询执行两路、同一过滤条件的 ES 检索：

1. `retrieval_text` 的 BM25 Top 10；
2. `retrieval_vector` 的 kNN Top 10；
3. 用 `1 / (60 + rank)` 进行 RRF 融合；
4. 用 BGE Reranker 对融合后的 Top 10 重排，保留 Top 5；
5. 按 `(rule_id, version)` 与当前 MySQL 规则再次核对，排除 ES 中的旧版本、禁用规则或不存在规则。

RAG 只为语义判断提供候选依据。ES 或 BGE 失败时，工作流返回确定性质检结果、增加 `rag_unavailable` 降级标记，并要求人工复核。
