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

+++SWARM: 2+ scopes in DESIGN.md

```
  team: refactoring-scan
  spawn: scanner-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Analyze {scope} for code quality issues.
  collect: lead collects scan results for cross-scope analysis
```

+++DETECT:
  D1: Dead Code — Functions, variables, or files never referenced
  D2: Unused Imports — Import statements with no usage
  D3: Premature Abstraction — Wrapper/helper used exactly once
  D4: Future Reservations — Code with TODO/FIXME that reserves unbuilt features
  D5: Duplicate Logic — Near-identical code blocks across files
  D6: Contradictory Impl — Two code paths that implement conflicting behavior
  D7: Inconsistent Naming — Same concept named differently across scopes

### Phase 2: REPORT

+++STOP: always

Do NOT refactor without approval.

+++Report:
| # | File:Line | Type | Finding | Suggested Fix |
|---|-----------|------|---------|---------------|

Wait for user to approve, reject, or modify each fix.

### Phase 3: EXECUTE

+++SWARM: 2+ approved fixes across independent scopes

```
  team: refactoring-execute
  spawn: fixer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply approved refactors to {scope}.
  collect: lead verifies refactors and runs validation
```

### Phase 4: VERIFY

Run full validation:

1. Run all validation commands defined in `DESIGN.md`
2. Re-scan for any new Detection Targets introduced by refactoring
3. Summarize: what was fixed, what remains, any regressions

## Constraints

+++NEVER: Refactor without +++STOP approval
+++NEVER: Hardcode scopes or validation commands — they come from DESIGN.md
+++NEVER: Change external behavior without explicit approval
+++NEVER: Auto-fix D6 (Contradictory Impl) — escalate to user first
