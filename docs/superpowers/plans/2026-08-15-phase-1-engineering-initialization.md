# Phase 1 Engineering Initialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Initialize a Python 3.12 development workspace without implementing any product inspection, API, Agent, Tool, RAG, LLM, or database business behavior.

**Architecture:** The repository will contain documented module boundaries, a uv-managed Python project, MySQL-only local Docker infrastructure, Alembic migration scaffolding, and configuration/test/lint tooling. Application modules remain placeholders; Streamlit, FastAPI, and LangGraph are dependencies only.

**Tech Stack:** Python 3.12, uv, FastAPI, Uvicorn, Pydantic, SQLAlchemy 2.x, Alembic, LangGraph, pytest, ruff, Docker Compose, MySQL 8.0.

## Global Constraints

- `docs/技术方案V2-final.md` is the highest-priority project specification.
- Food is the sole fully implemented MVP category; no food business behavior is included in this phase.
- Use `uv`, `pyproject.toml`, and `uv.lock`; do not use Poetry or `requirements.txt` as the dependency source of truth.
- Runtime dependencies are limited to FastAPI, Uvicorn, Pydantic, SQLAlchemy, Alembic, and LangGraph.
- Development dependencies are limited to pytest and ruff.
- Do not add Elasticsearch, Redis, Celery, embedding, or reranker dependencies.
- Docker Compose contains MySQL 8.0 only; FastAPI, Streamlit, and pytest run on the host in later phases.
- Do not create business database tables, API endpoints, LangGraph workflows, Tools, Skills, RAG, LLM calls, or evaluation logic.
- Do not commit secrets, `.env`, full prompts, or raw LLM output.

---

### Task 1: Establish repository guidance and the module skeleton

**Files:**
- Create: `AGENTS.md`
- Create: `.gitignore`
- Create: placeholder files in `app/`, `agent/`, `skills/`, `tools/`, `rag/`, `llm/`, `prompts/`, `workers/`, `review/`, `evaluation/`, `observability/`, `db/`, `scripts/`, and `tests/`
- Modify: `README.md`

**Produces:** Documented architecture rules, ownership boundaries, Git conventions, and empty module locations.

- [x] Create the required directories with placeholder files only.
- [x] Write `AGENTS.md` with Project Context, Source of Truth, Architecture Rules, Development Rules, Directory Ownership, and Git conventions.
- [x] Add ignores for local secrets, Python caches, virtual environments, tooling caches, OS files, and local worktrees.
- [x] Add an initial README covering scope and the intentionally unavailable business features.
- [x] Verify `git status --short` contains no generated cache or secret file.

### Task 2: Initialize the uv-managed Python project and quality tooling

**Files:**
- Create: `pyproject.toml`
- Create: `uv.lock`
- Create: `tests/test_project_structure.py`

**Produces:** A Python 3.12 project with the approved dependency and tool set.

- [x] Define project metadata, Python `>=3.12`, approved runtime dependencies, and a `dev` dependency group containing pytest and ruff.
- [x] Configure pytest test discovery and ruff target version, lint rules, and formatting behavior.
- [x] Write a structure smoke test asserting that the required top-level directories and configuration files exist.
- [x] Generate `uv.lock` with uv.
- [x] Run `uv run pytest` and `uv run ruff check .`.
- [x] Run `uv run ruff format --check .`.

### Task 3: Add local MySQL-only Docker infrastructure and configuration template

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `docker/.gitkeep`

**Produces:** A reproducible local MySQL 8.0 service configuration and a secret-free environment-variable template.

- [x] Define a `mysql` service using MySQL 8.0.
- [x] Configure a host port, named persistent volume, non-secret development placeholders, and a `mysqladmin ping` health check.
- [x] Include application, MySQL, and DeepSeek variable names in `.env.example`; leave the API key blank.
- [x] Verify the Compose file renders with `docker compose config`.
- [x] Do not add Elasticsearch or Redis services.

### Task 4: Establish database migration scaffolding without business schema

**Files:**
- Create: `alembic.ini`
- Create: `db/migrations/README`
- Create: `db/migrations/env.py`
- Create: `db/migrations/script.py.mako`
- Create: `db/migrations/versions/.gitkeep`

**Produces:** Alembic is initialized as the sole schema-change mechanism, with no domain tables or migrations.

- [x] Initialize Alembic under `db/migrations/`.
- [x] Keep the migration environment generic and do not create a revision or ORM model.
- [x] Document that the first actual schema change must be an Alembic revision in Phase 2.
- [x] Verify `uv run alembic --help` works.

### Task 5: Document local workflow and verify the initialization baseline

**Files:**
- Modify: `README.md`
- Modify: `docs/技术方案V2-final.md` (none)

**Produces:** A documented local setup procedure and verified initialization baseline.

- [x] Document prerequisite versions and installation commands for Python 3.12, uv, and Docker Compose.
- [x] Document copying `.env.example`, starting MySQL, syncing dependencies, and running pytest/ruff.
- [x] State clearly that no runnable API or Streamlit page exists until later phases.
- [x] Run the final verification suite: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `docker compose config`.
- [x] Review `git diff --check` and `git status --short`; preserve pre-existing `.DS_Store` and the supplied V2 specification without modification.

## Plan Self-Review

- Spec coverage: all user-required files, directories, approved dependencies, MySQL-only Compose design, environment variables, pytest, ruff, README, and initialization-only scope are covered.
- Scope check: no task creates business APIs, agent workflows, tools, skills, RAG, LLM calls, domain tables, or evaluation logic.
- Compatibility check: Python 3.12, uv, SQLAlchemy 2.x, and Alembic are consistently specified.
