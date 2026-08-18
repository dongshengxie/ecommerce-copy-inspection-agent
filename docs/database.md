# Phase 2 数据库说明

MySQL 8.0 在 Docker 中运行，宿主机通过 `MYSQL_PORT` 访问；默认端口为 `3307`，避免与本机 MySQL 的 `3306` 冲突。Schema 只能通过 Alembic 迁移变更。

## 数据库

| 数据库 | 用途 |
| --- | --- |
| `ecommerce_copy_inspection` | 本地开发库，保存已导入规则和实际同步质检记录。 |
| `ecommerce_copy_inspection_test` | 自动化集成测试专用库。每个测试会降级到 base、迁移到 head，并在结束后清理业务表。 |

首次创建 Docker 数据卷时，`docker/mysql/init/01-create-test-database.sh` 会创建测试库并授权 `app` 用户。已有旧数据卷不会重复执行初始化脚本；若测试库尚不存在，可按相同名称手动创建后再运行测试。

## 表职责

| 表 | 职责 |
| --- | --- |
| `products` | 商品稳定身份与类目。 |
| `product_revisions` | 商品原文 JSON、修订号和内容哈希。 |
| `quality_rules` | 已导入的版本化规则正文和状态。 |
| `inspection_tasks` | 任务状态、触发来源、规则版本和错误摘要。 |
| `inspection_results` | 自动风险、报告 JSON、复核标记和降级标记。 |
| `inspection_issues` | 可检索 Issue、证据、规则引用与置信度。 |
| `inspection_task_rules` | 一次成功质检实际加载的 `(rule_id, rule_version)` 集合，用于历史规则依据绑定。 |
| `optimization_attempts` | 显式文案优化的独立尝试和验证结果；不修改原商品修订或原质检报告。 |
| `agent_traces` | Skill/Tool 执行步骤、规则引用、决策、耗时和错误。 |

`alembic_version` 是 Alembic 的迁移版本元数据表，不属于业务表。

## 常用命令

```bash
docker compose up -d mysql
uv run alembic upgrade head
uv run alembic current
MYSQL_PORT=3307 uv run pytest tests/integration tests/evaluation -q
```

不要对开发库手工建表或修改 Schema；请创建新的 Alembic migration。
