<!-- last_verified: YYYY-MM-DD -->
# Feature: <name>

## Purpose
One sentence describing the problem this feature solves.

## Used By
- UI: <screen or flow>
- API: <endpoint>
- Job: <worker or cron> (if any)

## Core Functions
- function_or_module_a
- function_or_module_b

## Canonical Files
- Pattern exemplar: `path/to/canonical/implementation`

## Inputs
- name: type (source)

## Outputs
- name: type
- side effects (DB write, event, notification)

## Flow
- Step 1
- Step 2
- Step 3

## Edge Cases
- Case -> expected behavior

## UX States (if applicable)
- Empty
- Loading
- Error

## Verification
- Test files: `path/to/tests`
- Required cases: happy path + 2-5 edge cases
- Quick verify command: `<exact command>`
- Full verify command: `<exact command>`
- Pass criteria: what "green" looks like for this feature

## Related Docs
- [README.md](../../README.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [docs/app-workflows.md](../app-workflows.md)
