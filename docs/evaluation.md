# 食品质检评测

## 数据责任与范围

Golden Dataset、规则及其标签由项目方提供并确认；系统不生成、补全或替代业务 Ground Truth。仓库当前 10 条食品样例只用于回归测试，不可作为完整验收集。建议最低提供 30 条已标注样例，目标为 50–100 条，并覆盖 `pass`、`low`、`medium`、`high`、多 Issue、属性缺失、规则版本变更和人工复核边界。

## 离线模式

离线模式直接执行固定 Food LangGraph 工作流，不创建数据库连接、不请求 Elasticsearch、不构造 HTTP Client，也不调用 DeepSeek 或 BGE：

```bash
uv run python -m evaluation \
  --dataset evaluation/datasets/food_golden_dataset.json \
  --rules data/rules/food_rules.json \
  --output-dir evaluation/results
```

## 实时模式

实时模式通过 FastAPI 发起带 `X-Semantic-Inspection: enabled` 的质检请求，再读取报告和安全 Trace。运行前须启动 API，并配置以下变量：

- `BGE_API_BASE_URL`
- `BGE_API_KEY`
- `BGE_EMBEDDING_MODEL`
- `BGE_RERANKER_MODEL`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`

```bash
uv run python -m evaluation \
  --dataset evaluation/datasets/food_golden_dataset.json \
  --rules data/rules/food_rules.json \
  --live --api-base-url http://127.0.0.1:8000 \
  --output-dir evaluation/results
```

候选版本必须基于同一 `dataset_version` 的既有结果比较：

```bash
uv run python -m evaluation \
  --dataset evaluation/datasets/food_golden_dataset.json \
  --rules data/rules/food_rules.json \
  --candidate --baseline evaluation/results/<baseline>.json \
  --output-dir evaluation/results
```

## 结果与隐私

每次运行在 `evaluation/results/` 生成带 UTC 时间戳的 JSON；该目录已被 Git 忽略。结果包含 Dataset/规则/模型版本、指标、每条 Case 的标准化输出、预期差异和可选基线差异。它不包含商品原文、完整 Prompt、模型原始输出或任何密钥。

当指标没有可用分母时输出 `null`，例如离线评测没有语义调用时 Schema、Repair、检索指标均为 `null`，并不表示 0。

## 人工验收

离线结果验证确定性规则回归；实时结果验证 BGE 检索、DeepSeek 结构化输出、人工复核触发与版本元数据。云端模型变更、规则变更、Prompt 变更或阈值变更后，应由项目方复跑同一版本 Golden Dataset 并人工审核候选结果 Diff。
