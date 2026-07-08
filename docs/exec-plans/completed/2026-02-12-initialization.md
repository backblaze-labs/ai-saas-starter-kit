# Agent Doc Stack Initialization Plan

## Existing Files Inventory

| File | Disposition |
|------|-------------|
| `README.md` | **Rewrite** — has product info + architecture + setup. Restructure to spec. Move architecture detail to `ARCHITECTURE.md`. Add missing sections (features list, test commands, doc map, contribution basics). |
| `CLAUDE.md` | **Rewrite** — currently holds project conventions (structure, frontend/backend rules, commands). Per spec, CLAUDE.md should be 10–20 lines max, reference AGENTS.md for shared rules, contain read order + plan location + test commands + diff discipline. Conventions content moves to `AGENTS.md`. |
| `apps/web/README.md` | **Delete** — boilerplate from `create-next-app`. No durable truth. Redundant with root README. |
| `infra/railway/README.md` | **Keep as-is** — deployment instructions live here. Referenced from `ARCHITECTURE.md`. Not an Agent Doc Stack canonical file. |

## Files to Create

| File | Content Source |
|------|---------------|
| `ARCHITECTURE.md` | Extract from current README (directory tree), add component responsibilities, deployment info, data stores, data flows, trust boundaries, external services |
| `AGENTS.md` | Absorb conventions from current CLAUDE.md + add doc update rules, planning rules, testing rules, PR requirements per spec |
| `docs/app-workflows.md` | New — user journeys (dashboard view, file upload, file browse/preview/delete) |
| `docs/dev-workflows.md` | New — engineering workflows (new feature, bugfix, refactor, doc update, PR, testing) |
| `docs/features/file-upload.md` | New — upload feature spec |
| `docs/features/file-browser.md` | New — file browser feature spec |
| `docs/features/dashboard.md` | New — dashboard feature spec |
| `docs/features/metadata-extraction.md` | New — metadata extraction feature spec |

## Files to Update

| File | Changes |
|------|---------|
| `README.md` | Rewrite per spec: product overview, features list with links, architecture summary linking ARCHITECTURE.md, tech stack, setup, env vars, run/test commands, doc map, contribution basics |
| `CLAUDE.md` | Rewrite to 10–20 lines: reference AGENTS.md, doc read order, plan location, test commands, diff discipline |

## Files to Delete

| File | Reason |
|------|--------|
| `apps/web/README.md` | create-next-app boilerplate, no durable truth |

## Open Questions

None — all required information is available from the existing codebase and documentation.

## Execution Checklist

1. Delete `apps/web/README.md`
2. Create `ARCHITECTURE.md`
3. Create `AGENTS.md`
4. Create `docs/app-workflows.md`
5. Create `docs/dev-workflows.md`
6. Create `docs/features/file-upload.md`
7. Create `docs/features/file-browser.md`
8. Create `docs/features/dashboard.md`
9. Create `docs/features/metadata-extraction.md`
10. Rewrite `README.md`
11. Rewrite `CLAUDE.md`
12. Verify cross-links
