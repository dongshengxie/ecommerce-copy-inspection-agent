# Project Context

## Goal

This repository hosts an e-commerce product-copy inspection and optimization Agent for mainland China e-commerce text. It is an assistive quality-inspection system that identifies risks, cites supplied rules, and offers revision suggestions; it does not make legal rulings or assign compliance liability.

## MVP scope

- Food is the only category with complete MVP implementation.
- Supported content fields are product titles, selling points, descriptions, attributes, and marketing descriptions.
- MVP outputs include risk level, evidence-grounded issues, rule evidence, trace information, and user-requested optimization results with verification.

## Non-goals

- Multimodal inspection, legal adjudication, or compliance-liability decisions.
- Complete Beauty or Electronics skills.
- A complex operations console, approval system, or human-review workbench.
- Redis/Celery workers, batch processing, Elasticsearch, vector retrieval, embeddings, or rerankers during the initialization phase.

# Source of Truth

[`docs/技术方案V2-final.md`](docs/技术方案V2-final.md) is the highest-priority technical specification. Confirmed Phase 0 decisions take precedence over general engineering preferences. Stop and request confirmation if a proposed implementation conflicts with either source.

Business rules and Golden Dataset labels are supplied by the project owner. Do not invent or represent generated content as authoritative regulatory rules or business ground truth.

# Architecture Rules

- LangGraph uses a controlled workflow with a fixed main path and explicit conditional branches; do not use open-ended ReAct behavior.
- Tools perform deterministic, reproducible checks.
- Skills compose domain-specific capabilities, tools, prompts, and validation.
- RAG provides versioned rules and case evidence; it does not replace business decisions.
- LLMs perform constrained semantic judgment and generation only.
- Every formal Issue must contain evidence that can be located in the source text through `evidence_span`.
- An LLM must not negate a deterministic Tool conclusion.
- Optimization is explicitly requested by a user; it is never an automatic post-inspection side effect and must be verified.

# Development Rules

- Define or confirm Contracts before implementing consumers.
- Public Contracts (`ProductInput`, `Rule`, `Issue`, `ToolResult`, `SkillResult`, `InspectionState`, `InspectionReport`, and `TraceEvent`) cannot be changed without human confirmation.
- Every feature requires appropriate automated tests.
- All database schema changes use Alembic migrations; never apply untracked manual schema changes.
- Never commit `.env`, real credentials, API keys, full prompts, raw model outputs, or sensitive traces.
- Do not add Elasticsearch, Redis, Celery, embedding, or reranker dependencies before their approved milestones.

# Directory Ownership

| Responsibility | Directories |
| --- | --- |
| Platform and application boundary | `app/`, `contracts/`, `db/`, `observability/` |
| Controlled workflow | `agent/` |
| Domain inspection | `skills/`, `tools/` |
| Knowledge retrieval | `rag/`, `prompts/` |
| Model integration and governance | `llm/` |
| Async runtime | `workers/` |
| Human review and feedback | `review/` |
| Quality and regression | `evaluation/`, `tests/` |
| Documentation and data operations | `docs/`, `scripts/` |

Cross-directory work must document Contract changes, dependency direction, and test ownership before implementation.

# Git Conventions

- Develop on `codex/<type>/<short-description>` branches unless the user requests otherwise.
- Keep each commit focused on one coherent purpose; do not mix feature work, unrelated formatting, and refactoring.
- Use Conventional Commit messages, such as `chore: initialize project structure`, `docs: add setup guidance`, or `test: add contract coverage`.
- Do not commit directly to the main branch for feature work without explicit user authorization.
- Explain Contract, migration, rule-format, and compatibility effects in the relevant commit message or body.
