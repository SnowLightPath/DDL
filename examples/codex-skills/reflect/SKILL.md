---
name: reflect
description: Update documents based on implementation results
metadata:
  short-description: Code to Design
---

# reflect

Update documents based on implementation results.

## Usage

- `$reflect` — Check entire project alignment
- `$reflect <path>` — Check specific file/directory

## Phases

### Phase 0: INIT

1. Read `AGENTS.md`
2. Read `DESIGN.md` — extract scopes and principles
3. If no `DESIGN.md` exists → refuse ("Nothing to reflect against")

### Phase 1: READ

For each scope in `DESIGN.md`, sequentially scan current implementation state. Then self-inspect `DESIGN.md` for internal consistency.

### Phase 2: COMPARE

Compare implementation against `DESIGN.md` principles. Classify divergences:
- **Code drifted** — implementation violates principle
- **Philosophy outdated** — code shows better approach
- **New pattern** — code introduced something `DESIGN.md` doesn't cover

Run Detection Target scan:

| ID | Name | Trigger |
|----|------|---------|
| D1 | Drift | Implementation contradicts a stated principle |
| D2 | New Pattern | Code exhibits a pattern not captured in `DESIGN.md` |
| D3 | Outdated Principle | Principle references removed/changed behavior |
| D4 | Stale Reference | `DESIGN.md` links or paths no longer exist |
| D5 | Self-Contradiction | Two principles in `DESIGN.md` conflict with each other |

### Phase 3: REPORT

**STOP gate** — Present divergence report to user. Do NOT modify `DESIGN.md` without approval.

Wait for user to approve, reject, or modify each recommendation.

### Phase 4: APPLY

Apply only approved changes.

After applying:
1. Summarize what changed
2. Suggest next command if applicable

## Constraints

- Never modify `DESIGN.md` without STOP gate approval
- Can reflect on `DESIGN.md` itself (meta-reflection)
- Scopes come from `DESIGN.md`, not hardcoded paths
