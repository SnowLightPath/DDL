# reflect

Update documents based on implementation results.

## Usage

- `/reflect` — Check entire project alignment
- `/reflect <path>` — Check specific file/directory

## Phases

### Phase 0: INIT

1. Read `.claude/commands/DDL-PROTOCOL-SKILL.md`
2. Read `CLAUDE.md`
3. Read `design.md` — extract scopes and principles
4. If no `design.md` exists → refuse ("Nothing to reflect against")

### Phase 1: READ

```
+++SWARM: 2+ scopes in design.md
  team: reflect-read
  spawn: reader-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Scan its scope for current implementation state.
    Report findings to team-lead when done.
  collect: lead collects read results into a unified context
```

Additionally: spawn `reader-design` to self-inspect `design.md` for internal consistency.

### Phase 2: COMPARE

Lead integrates results and performs cross-scope analysis:

1. Compare each scope's implementation against `design.md` principles
2. Classify divergences:
   - **Code drifted** — implementation violates principle
   - **Philosophy outdated** — code shows better approach
   - **New pattern** — code introduced something `design.md` doesn't cover

+++DETECT:
  D1: Drift — Implementation contradicts a stated principle
  D2: New Pattern — Code exhibits a pattern not captured in design.md
  D3: Outdated Principle — Principle references removed/changed behavior
  D4: Stale Reference — design.md links or paths no longer exist
  D5: Self-Contradiction — Two principles in design.md conflict with each other

### Phase 3: REPORT

+++STOP: always

Do NOT modify `design.md` without approval.

+++Report:
| # | Type | Principle | Finding | Recommendation |
|---|------|-----------|---------|----------------|

Wait for user to approve, reject, or modify each recommendation.

### Phase 4: APPLY

```
+++SWARM: 2+ approved changes across scopes
  team: reflect-apply
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply only approved changes to its scope.
    Report completion to team-lead when done.
  collect: lead summarizes what changed
```

After applying:
1. Summarize what changed
2. Suggest next command if applicable

## Constraints

+++NEVER: Modify design.md without +++STOP approval
+++NEVER: Hardcode scopes — they come from design.md
+++NEVER: Skip meta-reflection — can reflect on design.md itself
