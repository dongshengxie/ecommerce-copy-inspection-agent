# Phase 2 Food Sync MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a synchronous, deterministic food-copy inspection API with MySQL persistence and Golden Dataset regression coverage.

**Architecture:** FastAPI delegates to one synchronous application service. The service loads enabled food rules from MySQL, calls deterministic Food Tools through FoodQualitySkill, aggregates the maximum Issue risk, and persists task, result, issue, and Trace records. No LangGraph, LLM, RAG, Redis/Celery, review workflow, Streamlit, or optimization code is included.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic, PyMySQL, MySQL 8.0, pytest, ruff.

## Global Constraints

- The confirmed v1.0 food rules and Golden Dataset are project-owner data; do not invent rules or labels.
- Food is the only supported category; non-food input returns HTTP 422.
- Risk is `high` when any Issue is high; otherwise it is the highest present Issue risk; no Issue is `pass`.
- The first migration creates only `products`, `product_revisions`, `quality_rules`, `inspection_tasks`, `inspection_results`, `inspection_issues`, and `agent_traces`.
- MySQL connections use PyMySQL and integration tests use `MYSQL_TEST_DATABASE`.
- Every behavior follows red-green-refactor and has an automated test.

## File Map

| Files | Responsibility |
| --- | --- |
| `contracts/models.py` | Enums and shared Pydantic Contracts |
| `app/config.py`, `db/session.py` | Environment configuration and SQLAlchemy session creation |
| `db/models/core.py`, `db/repositories/*.py` | Approved persistence model and Repository APIs |
| `scripts/import_rules.py` | Validated idempotent rule import |
| `tools/food/*.py`, `skills/food/quality.py` | Deterministic inspection only |
| `app/services/inspection.py`, `app/api/inspections.py`, `app/main.py` | Synchronous service and three HTTP endpoints |
| `tests/contract`, `tests/unit`, `tests/integration`, `tests/evaluation` | Contract, unit, MySQL, API, and Golden regression tests |

### Task 1: Normalize and commit the owner-confirmed v1.0 data

**Files:** Modify `evaluation/datasets/food_golden_dataset.json`, `tests/evaluation/test_food_seed_data.py`; add the confirmed rules, dataset, and Phase 2 spec to Git.

**Produces:** Every case `notes` is exactly `项目方已确认的 v1.0 基线`; existing labels, rule IDs, evidence, and input are unchanged.

- [ ] Add a test asserting `{case["notes"] for case in cases} == {"项目方已确认的 v1.0 基线"}`.
- [ ] Run `uv run pytest tests/evaluation/test_food_seed_data.py::test_food_seed_data_is_owner_confirmed -v`; observe the expected failure against the former draft text.
- [ ] Update only the ten note values, then run JSON parsing and `uv run pytest tests/evaluation/test_food_seed_data.py -v`.
- [ ] Commit with `test: 提交食品规则与评测基线`.

### Task 2: Add PyMySQL, configuration, and frozen Contracts

**Files:** Modify `pyproject.toml`, `uv.lock`, `.env.example`; create `app/config.py`, `contracts/models.py`, `tests/contract/test_models.py`.

**Consumes:** The v1.0 JSON shapes and the Phase 2 design.

**Produces:** `RiskLevel`, `TaskStatus`, `FoodAttributes`, `ProductInput`, `Rule`, `Issue`, `ToolResult`, `SkillResult`, `TraceEvent`, `InspectionReport`, `Settings.from_environment()`, and `Settings.database_url()`.

- [ ] Write tests that reject category `美妆`, blank Issue `evidence_span`, and missing required food attributes.
- [ ] Run `uv run pytest tests/contract/test_models.py -v`; observe the missing-module failure.
- [ ] Add PyMySQL, `MYSQL_TEST_DATABASE=ecommerce_copy_inspection_test`, and the models. Food attributes require `ingredients`, `shelf_life`, `storage_method`, and `origin`; optional extensions are `applicable_people`, `net_content`, and `brand`.
- [ ] Run `uv lock`, the Contract tests, `uv run ruff check contracts app/config.py`, and `uv run ruff format --check contracts app/config.py`.
- [ ] Commit with `feat: 定义食品质检核心契约`.

### Task 3: Create persistence models and the exact initial migration

**Files:** Create `db/session.py`, `db/models/core.py`, `db/repositories/rules.py`, `db/repositories/inspections.py`, one migration in `db/migrations/versions/`, and `tests/integration/test_migration.py`.

**Produces:** `create_engine_and_session(settings)`, `RuleRepository`, `InspectionRepository`, and exactly seven new tables.

- [ ] Write a migration test that upgrades an empty `MYSQL_TEST_DATABASE` and asserts the table set equals the seven approved names.
- [ ] Run `MYSQL_DATABASE=$MYSQL_TEST_DATABASE uv run pytest tests/integration/test_migration.py -v`; observe the missing migration/session failure.
- [ ] Implement string UUID primary keys; unique `(product_id, revision)` and `(rule_id, version)` constraints; task foreign keys; JSON document/report fields; and task/result/issue/trace relationships. Do not add any other table.
- [ ] Start MySQL with `docker compose up -d mysql`, run the migration test, and confirm its fixture removes only the test database.
- [ ] Commit with `feat: 添加质检核心数据持久化`.

### Task 4: Implement validated rule import and enabled-rule reads

**Files:** Create `scripts/import_rules.py`, modify `db/repositories/rules.py`, create `tests/integration/test_rule_import.py`.

**Produces:** `RuleRepository.import_rules(rules) -> int` and `RuleRepository.list_enabled_food_rules() -> list[Rule]`.

- [ ] Write a test that imports the ten rules, reimports them, expects counts `10` then `0`, and expects enabled food rules ordered by `rule_id`.
- [ ] Run `MYSQL_DATABASE=$MYSQL_TEST_DATABASE uv run pytest tests/integration/test_rule_import.py -v`; observe the missing-method failure.
- [ ] Validate UTF-8 JSON with `Rule.model_validate`; insert only unseen `(rule_id, version)` values; filter reads to `category="食品"` and `status="enabled"`.
- [ ] Run the integration test and `MYSQL_DATABASE=$MYSQL_TEST_DATABASE uv run python scripts/import_rules.py data/rules/food_rules.json` twice.
- [ ] Commit with `feat: 支持食品规则导入与查询`.

### Task 5: Implement deterministic Food Tools and FoodQualitySkill

**Files:** Create `tools/food/checks.py`, `tools/food/risk.py`, `skills/food/quality.py`, `tests/unit/test_food_checks.py`, `tests/unit/test_food_risk.py`, `tests/unit/test_food_quality_skill.py`.

**Produces:** `check_rule_expressions(product, rules)`, `check_required_food_attributes(product, rules)`, `check_food_spec_consistency(product, rules)`, `aggregate_risk(issues)`, and `FoodQualitySkill.inspect(product, rules)`.

- [ ] Write tests from case 002 for `治疗失眠`, case 004 for six combined findings, case 007 for `500g`/`250g` conflict, case 001 for no findings, and a low-plus-high aggregation case.
- [ ] Run the focused unit tests; observe import failures.
- [ ] Implement literal `bad_examples` matching only within each rule `field_scope`; deterministic confidence is `1.0`. Implement the exact attribute map: `ingredients→food_attribute_005`, `shelf_life→food_attribute_006`, `storage_method→food_attribute_007`, `origin→food_attribute_008`. Compare specifications only when units are comparable; do not normalize unrelated units or create title-length findings.
- [ ] Run all Food Tool tests and `tests/evaluation/test_food_seed_data.py`.
- [ ] Commit with `feat: 实现食品确定性质检工具`.

### Task 6: Implement synchronous inspection service and persistence

**Files:** Create `app/services/inspection.py`, modify `db/repositories/inspections.py`, create `tests/integration/test_inspection_service.py`.

**Produces:** `InspectionApplicationService.create_inspection(product: ProductInput) -> InspectionReport`.

- [ ] Write a test submitting case 004 and asserting `high`, `review_required is True`, six Issues, and trace step names `food_quality_skill` and `risk_aggregator`.
- [ ] Run `MYSQL_DATABASE=$MYSQL_TEST_DATABASE uv run pytest tests/integration/test_inspection_service.py -v`; observe the missing-service failure.
- [ ] Persist product/revision and a `running` task; load enabled rules; call FoodQualitySkill; aggregate risk; persist result/issues/traces; mark task `success`. On a post-task failure, mark it `failed`, persist a failure trace, and do not return a success report.
- [ ] Run the service test against MySQL and verify stored report, issue, and trace rows.
- [ ] Commit with `feat: 添加同步食品质检服务`.

### Task 7: Add the minimal FastAPI interface

**Files:** Create `app/main.py`, `app/api/inspections.py`, `tests/integration/test_inspection_api.py`.

**Produces:** `create_app() -> FastAPI`; `POST /api/v2/inspections`; `GET /api/v2/inspections/{task_id}`; `GET /api/v2/inspections/{task_id}/result`.

- [ ] Write API tests that create case 005 and fetch a medium result, reject a non-food payload with 422, and return 404 for an unknown task ID.
- [ ] Run `MYSQL_DATABASE=$MYSQL_TEST_DATABASE uv run pytest tests/integration/test_inspection_api.py -v`; observe missing-app failure.
- [ ] Implement POST as synchronous and return HTTP 201 with `task_id`, status, and `result_url`; map Contract/category errors to 422, unknown IDs to 404, and internal inspection failures to a non-success response without exception details.
- [ ] Run the API tests and `uv run python -c 'from app.main import create_app; assert "/api/v2/inspections" in create_app().openapi()["paths"]'`.
- [ ] Commit with `feat: 提供同步质检 API`.

### Task 8: Add full Golden Dataset regression and operating documentation

**Files:** Create `tests/evaluation/test_food_sync_regression.py`, `docs/api.md`, `docs/database.md`; modify `README.md`.

**Produces:** A 10-case end-to-end regression that compares normalized Issues, Rule IDs, and risk levels to the owner-confirmed baseline.

- [ ] Write a parametrized test that runs every Golden case through `InspectionApplicationService.create_inspection`, then compares `automated_risk_level`, normalized Issues, and rule IDs to that case's expected values.
- [ ] Run `MYSQL_DATABASE=$MYSQL_TEST_DATABASE uv run pytest tests/evaluation/test_food_sync_regression.py -v`; initially it must expose any wiring mismatch.
- [ ] Correct only Contract adapters, Tools, persistence mapping, or report normalization; do not alter owner rules or expected labels to satisfy implementation failures.
- [ ] Document MySQL startup, migration upgrade, rule import, API startup, request/response examples, table purposes, regression command, and Phase 2 exclusions.
- [ ] Run `docker compose up -d mysql && MYSQL_DATABASE=$MYSQL_TEST_DATABASE uv run pytest && uv run ruff check . && uv run ruff format --check . && docker compose config && git diff --check`.
- [ ] Commit with `test: 覆盖食品同步质检回归`.

## Plan Self-Review

- Coverage: all confirmed data, Contract, PyMySQL, seven-table, import, deterministic Tool, service, API, Trace, regression, and documentation requirements map to Tasks 1–8.
- Exclusions: no task adds LangGraph, LLM, RAG, Elasticsearch, Redis, Celery, review workflow, Streamlit, or optimization.
- Consistency: later tasks consume exact names produced by earlier tasks.
