# Agent-Friendly Repo Restructuring

## Status: Implemented

## Summary

Restructured the repo for agent-optimized development following OpenAI guidance. Four phases:

1. **Documentation & Knowledge Base** — new docs directory structure, golden-principles.md, SECURITY.md, RELIABILITY.md, QUALITY_SCORE.md, rewritten AGENTS.md as concise TOC, updated ARCHITECTURE.md and README.md
2. **API Layering** — restructured services/api/ to strict layered architecture (types/config/repo/service/runtime), added structured JSON logging, /metrics endpoint, request timing middleware
3. **Mechanical Guardrails** — ruff config with strict rules, stricter ESLint, pre-commit hooks, structural tests enforcing layering/boundaries/file-size, root scripts
4. **Testing & Observability** — pytest harness with conftest.py, health/metrics integration tests, Playwright e2e scaffolding, maintenance checklist

## Verification

- `ruff check .` — all checks passed
- `pytest -v` — 6/6 tests passed (4 structural + 2 integration)
- `pnpm build` — frontend builds successfully
- `pnpm lint` — 3 pre-existing react-hooks errors (not introduced by this change)
