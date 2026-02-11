---
name: refactoring
description: Audit and fix code quality issues
metadata:
  short-description: Code quality audit
---

# refactoring

Audit and fix code quality issues.

## Usage

- `$refactoring` — Audit all scopes
- `$refactoring <path>` — Audit specific file or directory

## Phases

### Phase 0: INIT

1. Read `AGENTS.md`
2. Read `DESIGN.md` — extract scopes, principles, validation commands
3. If no `DESIGN.md` exists → scan project root for common patterns

### Phase 1: SCAN

For each scope in `DESIGN.md`, sequentially analyze for code quality issues.

Check the following Detection Targets per scope:

| ID | Name | Trigger |
|----|------|---------|
| D1 | Dead Code | Functions, variables, or files never referenced |
| D2 | Unused Imports | Import statements with no usage |
| D3 | Premature Abstraction | Wrapper/helper used exactly once |
| D4 | Future Reservations | Code with TODO/FIXME that reserves unbuilt features |
| D5 | Duplicate Logic | Near-identical code blocks across files |
| D6 | Contradictory Impl | Two code paths that implement conflicting behavior |
| D7 | Inconsistent Naming | Same concept named differently across scopes |

### Phase 2: REPORT

**STOP gate** — Present findings to user. Do NOT refactor without approval.

### Phase 3: EXECUTE

Apply approved refactors.

### Phase 4: VERIFY

Run full validation:

1. Run all validation commands defined in `DESIGN.md`
2. Re-scan for any new Detection Targets introduced by refactoring
3. Summarize: what was fixed, what remains, any regressions

## Constraints

- Never refactor without STOP gate approval
- Scopes and validation commands come from `DESIGN.md`, not hardcoded
- Refactoring must not change external behavior (unless approved)
- If D6 (Contradictory Impl) detected → escalate to user before any fix
