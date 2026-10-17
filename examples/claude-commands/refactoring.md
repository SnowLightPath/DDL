# refactoring

Audit and fix code quality issues.

## Usage

- `/refactoring` — Audit all scopes
- `/refactoring <path>` — Audit specific file or directory

## Phases

### Phase 0: INIT

1. Read the DDL protocol for the current runtime: repo-local `commands/DDL-PROTOCOL-SKILL.md` when present; otherwise, in Claude Code, `.claude/commands/DDL-PROTOCOL-SKILL.md`, then `$HOME/.claude/commands/DDL-PROTOCOL-SKILL.md`; in Codex, `$HOME/.codex/commands/DDL-PROTOCOL-SKILL.md`, then the protocol sections of `AGENTS.md`.
2. Read project-local runtime guidance when present: `AGENTS.md` for Codex, `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, and any applicable command overlay.
3. Read `design.md` — extract scopes, principles, Binding Decisions, validation commands
4. If no `design.md` exists → scan project root for common patterns
5. If a path is given, audit only that path and the scopes it covers (§2.3 of the protocol)

### Phase 1: SCAN

+++SWARM: 2+ scopes in design.md

```
  team: refactoring-scan
  spawn: scanner-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Analyze {scope} for code quality issues.
    Report findings to the lead when done.
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

**Pre-condition.** Enter this phase only after explicit user approval at the Phase 2 STOP gate (per §1.5 of the protocol). If the most recent user message is not an approval token, return to Phase 2 and re-emit the report.

+++SWARM: 2+ approved fixes across independent scopes

```
  team: refactoring-execute
  spawn: fixer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply approved refactors to {scope}.
    Report completion to the lead when done.
  collect: lead verifies refactors and runs validation
```

### Phase 4: VERIFY

Run full validation:

1. Run all validation commands defined in `design.md` in parallel, comparing each output with its expected value
2. Re-scan for any new Detection Targets introduced by refactoring
3. Summarize: what was fixed, what remains, any regressions

+++DETECT:
  D8: Regression — A validation command exits non-zero, cannot run, or prints other than its expected value after the refactor

+++STOP: on D8

## Constraints

+++NEVER: Refactor without +++STOP approval
+++NEVER: Hardcode scopes or validation commands — they come from design.md
+++NEVER: Change external behavior without explicit approval
+++NEVER: Auto-fix D6 (Contradictory Impl) — escalate to user first
+++NEVER: Replace or bypass a Binding Decision — that is a design change for /draft or /reflect, not a refactoring
