# 电商商品文案质检与优化 Agent

面向中国大陆电商商品文本场景的辅助质检系统。系统将确定性检查、项目方提供的规则依据、受控语义判断与可追踪结果结合，用于识别商品文案风险并提供修改建议。

## MVP 范围

- 食品是唯一完整实现类目。
- 处理商品标题、卖点、详情、属性和营销描述。
- 优化由用户显式请求；审核完成后不会自动改写文案。
- 规则和 Golden Dataset 由项目方提供，系统负责加载、引用、版本记录和评测执行。

当前已完成 Phase 5 的核心能力：规则导入、确定性 Food Tools、食品 Skill、MySQL 持久化、Elasticsearch 派生规则索引、BGE 混合检索、DeepSeek 结构化语义判断、受控 LangGraph 工作流、显式文案优化与二次质检、规则依据查询、Trace 查询，以及离线/实时评测 Runner。Redis/Celery、人审工作台与 Streamlit Demo 尚未实现。

## 技术栈

- Python 3.12
- uv
- FastAPI、Uvicorn、Pydantic
- SQLAlchemy 2.x、Alembic、MySQL 8.0
- LangGraph
- pytest、ruff
- Elasticsearch 8、硅基流动 BGE API、DeepSeek API
- Docker Compose（MySQL、Elasticsearch）

## 环境准备

安装以下工具：

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- Docker Desktop（含 Docker Compose）

复制环境变量模板并按本机环境调整：

```bash
cp .env.example .env
```

## 本地启动方式（当前阶段）

启动基础设施：

```bash
docker compose up -d mysql elasticsearch
docker compose ps
```

安装并锁定 Python 依赖：

```bash
uv sync --all-groups
```

应用数据库迁移并导入项目方规则：

```bash
uv run alembic upgrade head
uv run python scripts/import_rules.py data/rules/food_rules.json
uv run python scripts/sync_rules_to_es.py
```

`sync_rules_to_es.py` 只从 MySQL 读取已启用的食品规则，并以 BGE 向量写入 Elasticsearch；MySQL 仍是规则唯一事实来源。执行前请在本机 `.env` 填写 BGE 配置。应用在需要语义质检时还需要 `DEEPSEEK_API_KEY`；缺少任一外部模型配置时，确定性质检仍会返回，但会标记降级并要求人工复核。

启动同步 API：

```bash
set -a
source .env
set +a
uv run uvicorn app.main:app --reload
```

运行工程质量检查：

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
docker compose config
```

启动后可访问 `http://127.0.0.1:8000/docs`。详细接口见 [docs/api.md](docs/api.md)，数据库说明见 [docs/database.md](docs/database.md)。

## 评测

项目方提供 Golden Dataset 和规则 JSON；系统只负责加载、执行、对比与输出指标，不生成业务真值。当前 10 条样例仅用于回归，正式验收建议至少提供 30 条、目标为 50–100 条已标注样例。

默认离线评测不访问 MySQL、Elasticsearch、HTTP 或模型服务：

```bash
uv run python -m evaluation \
  --dataset evaluation/datasets/food_golden_dataset.json \
  --rules data/rules/food_rules.json \
  --output-dir evaluation/results
```

实时评测必须先启动 FastAPI，并在 `.env` 中配置 `BGE_API_BASE_URL`、`BGE_API_KEY`、`BGE_EMBEDDING_MODEL`、`BGE_RERANKER_MODEL`、`DEEPSEEK_API_KEY` 和 `DEEPSEEK_MODEL`：

```bash
set -a
source .env
set +a
uv run python -m evaluation \
  --dataset evaluation/datasets/food_golden_dataset.json \
  --rules data/rules/food_rules.json \
  --live --api-base-url http://127.0.0.1:8000 \
  --output-dir evaluation/results
```

候选版本对比必须指定同一 `dataset_version` 的基线结果：

```bash
uv run python -m evaluation \
  --dataset evaluation/datasets/food_golden_dataset.json \
  --rules data/rules/food_rules.json \
  --candidate --baseline evaluation/results/<baseline>.json \
  --output-dir evaluation/results
```

结果文件只保存标准化 Issue、指标、版本和安全 Trace 元数据；不会保存商品原文、完整 Prompt、原始模型输出或密钥。指标中的 `null` 表示该次运行没有相应分母，不代表 0 分。详细说明见 [docs/evaluation.md](docs/evaluation.md)。

## 数据库与迁移

MySQL 8.0 与 Elasticsearch 8 运行于本地 Docker；FastAPI、pytest 和后续 Streamlit 运行在宿主机。MySQL 默认映射宿主机 `3307` 端口，Elasticsearch 映射 `9200`。所有 Schema 变更必须通过 Alembic migration 管理。测试使用独立的 `MYSQL_TEST_DATABASE`，不会写入开发库。

## 后续开发流程

1. 阅读 `docs/技术方案V2-final.md` 与根目录 `AGENTS.md`。
2. 先确认或冻结涉及的 Contract。
3. 按已批准 Milestone 实现，并为功能添加测试。
4. 执行 pytest、ruff 与相关集成验证。
5. 保持提交聚焦，且不提交 `.env`、敏感配置或项目方业务真值数据。
