# 电商商品文案质检与优化 Agent

面向中国大陆电商商品文本场景的辅助质检系统。系统将确定性检查、项目方提供的规则依据、受控语义判断与可追踪结果结合，用于识别商品文案风险并提供修改建议。

## MVP 范围

- 食品是唯一完整实现类目。
- 处理商品标题、卖点、详情、属性和营销描述。
- 优化由用户显式请求；审核完成后不会自动改写文案。
- 规则和 Golden Dataset 由项目方提供，系统负责加载、引用、版本记录和评测执行。

当前仅完成工程初始化。尚未实现 API、LangGraph 工作流、Tools、Skills、RAG、LLM 调用、业务数据库表或 Streamlit 页面。

## 技术栈

- Python 3.12
- uv
- FastAPI、Uvicorn、Pydantic
- SQLAlchemy 2.x、Alembic、MySQL 8.0
- LangGraph
- pytest、ruff
- Docker Compose（本阶段仅 MySQL）

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

启动 MySQL：

```bash
docker compose up -d mysql
docker compose ps
```

安装并锁定 Python 依赖：

```bash
uv sync --all-groups
```

运行工程质量检查：

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
docker compose config
```

当前阶段没有可启动的 FastAPI 服务或 Streamlit 页面；这些能力将在后续 Milestone 实现。

## 数据库与迁移

MySQL 8.0 运行于本地 Docker。所有未来 Schema 变更必须通过 Alembic migration 管理；工程初始化阶段不创建业务表。

## 后续开发流程

1. 阅读 `docs/技术方案V2-final.md` 与根目录 `AGENTS.md`。
2. 先确认或冻结涉及的 Contract。
3. 按已批准 Milestone 实现，并为功能添加测试。
4. 执行 pytest、ruff 与相关集成验证。
5. 保持提交聚焦，且不提交敏感配置或业务真值数据。
