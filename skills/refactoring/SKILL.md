---
name: refactoring
description: Audit and fix code quality issues
argument-hint: "[path]"
disable-model-invocation: true
metadata:
  short-description: Code quality audit
---

# refactoring

Audit and fix code quality issues.

## Usage

- `/refactoring` — Audit all scopes
- `/refactoring <path>` — Audit specific file or directory

## Phases

### Phase 0: INIT

A command run from a user-level install follows the project's own copy when one exists (`.claude/skills/<name>/SKILL.md` in Claude Code, `.agents/skills/<name>/SKILL.md` in Codex, or the file the project's instruction file names as the command's source): the project's version is the one that runs.

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex). Follow its Start steps before continuing.
2. Read the project's guidance file when it is not already in context (the host loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract scopes, Binding Decisions, validation commands
4. If no `design.md` exists → scan project root for common patterns
5. If a path is given, audit only that path and the scopes it covers

If Binding Decisions exist, read the Notebook operation before checking them.

When a STOP needs a decision, read the Approval operation and its implementation for the current host before presenting the decision. When a SWARM fires, read the Parallel work operation and its implementation before fan-out.

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
  D8: Design Change — a fix would change external behavior, a principle or a Binding Decision

D6 and D8 ask with options: apply the fix, leave it unapplied, or revise it; a Binding Decision change is left for /draft or /reflect.

+++STOP: on D6
+++STOP: on D8

### Phase 2: EXECUTE

Read the Run operation and its implementation for the current host, then make a snapshot (the gate's `snapshot`) before the first refactor.

+++DETECT:
  D9: No Snapshot — the snapshot cannot be made (no gate, no Git repository, or a failure)

D9 asks with options: apply without a snapshot, or apply nothing.

+++STOP: on D9

Apply every refactor inside the scopes Phase 0 selected, and a D6 or D8 fix only as its answer chose.

+++SWARM: 2+ fixes across independent scopes

```
  team: refactoring-execute
  spawn: fixer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply to {scope} the refactors listed in this prompt, and nothing else.
    Report completion to the lead when done.
  collect: lead verifies refactors and runs validation
```

### Phase 3: VERIFY

Run full validation:

1. Run all validation commands defined in `design.md` in parallel, comparing each output with its expected value
2. Re-scan for any new Detection Targets introduced by refactoring
3. Summarize: what was fixed, what remains, any regressions

+++DETECT:
  D10: Regression — A validation command exits non-zero, cannot run, or prints other than its expected value after the refactor

+++STOP: on D10

### Phase 4: REPORT

+++STOP: always

Report what was applied; ask nothing (Approval Exceptions: informational).

+++Report:
Outcome: the applied refactors, numbered with stable IDs, each with its file and correction, and the snapshot ref that undoes them.
Consequence: the refactors stand in the working tree, uncommitted; restoring the snapshot undoes them all.
Review detail: each refactor ID, file/line, detection type, finding, and correction; each finding left unapplied, with its reason; each validation command's result and any regression.
Choices: none; the report asks nothing. With no findings, state that nothing changed.

## Constraints

+++NEVER: Refactor outside the scopes Phase 0 selected
+++NEVER: Hardcode scopes or validation commands — they come from design.md
+++NEVER: Change external behavior or a principle without explicit approval
+++NEVER: Auto-fix D6 (Contradictory Impl) — escalate to user first
+++NEVER: Replace or bypass a Binding Decision — that is a design change for /draft or /reflect, not a refactoring
