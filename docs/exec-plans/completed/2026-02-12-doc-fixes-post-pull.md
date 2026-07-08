# Post-Pull Doc Fixes Plan

## Scope
- Align documented frontend framework version with the actual dependency.
- Update setup prerequisites to include required B2 delete permission.

## Files To Update
- `README.md`
- `ARCHITECTURE.md`
- `AGENTS.md`

## Execution Steps
1. Replace `Next.js 15` references with `Next.js 16` in docs that summarize the stack.
2. Update B2 application key permissions to include `deleteFiles` in setup docs.
3. Re-scan docs for remaining `Next.js 15` references.

