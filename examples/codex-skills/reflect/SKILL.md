---
name: reflect
description: Update documents based on implementation results
metadata:
  short-description: Code to Design
---

# reflect

Detect divergence between implementation and DESIGN.md, then reconcile.

## Usage

- `$reflect` — Check entire project alignment
- `$reflect <path>` — Check specific file/directory

## Phases

### Phase 0: INIT

1. Read `AGENTS.md`
2. Read `DESIGN.md` — extract scopes and principles
3. If no `DESIGN.md` exists → refuse ("Nothing to reflect against")

### Phase 1: READ

+++SWARM: 2+ scopes in DESIGN.md

```
  team: reflect-read
  spawn: reader-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Scan {scope} for current implementation state.
  collect: lead also inspects DESIGN.md for internal consistency, then integrates all results
```

### Phase 2: COMPARE

Lead integrates results and performs cross-scope analysis:

1. Compare each scope's implementation against `DESIGN.md` principles
2. Classify divergences:
   - **Code drifted** — implementation violates principle
   - **Philosophy outdated** — code shows better approach
   - **New pattern** — code introduced something `DESIGN.md` doesn't cover

+++DETECT:
  D1: Drift — Implementation contradicts a stated principle
  D2: New Pattern — Code exhibits a pattern not captured in DESIGN.md
  D3: Outdated Principle — Principle references removed/changed behavior
  D4: Stale Reference — DESIGN.md links or paths no longer exist
  D5: Self-Contradiction — Two principles in DESIGN.md conflict with each other

### Phase 3: REPORT

+++STOP: always

Do NOT modify `DESIGN.md` without approval.

+++Report:
| # | Type | Principle | Finding | Recommendation |
|---|------|-----------|---------|----------------|

Wait for user to approve, reject, or modify each recommendation.

### Phase 4: APPLY

+++SWARM: 2+ approved changes across scopes

```
  team: reflect-apply
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply only approved changes to {scope}.
  collect: lead summarizes what changed
```

After applying:
1. Summarize what changed
2. Suggest next command if applicable

## Constraints

+++NEVER: Modify DESIGN.md without +++STOP approval
+++NEVER: Hardcode scopes — they come from DESIGN.md
+++NEVER: Skip meta-reflection — can reflect on DESIGN.md itself
