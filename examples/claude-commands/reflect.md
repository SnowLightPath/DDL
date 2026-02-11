# reflect

Update documents based on implementation results.

## Usage

- `/reflect` — Check entire project alignment
- `/reflect <path>` — Check specific file/directory

## Phases

### Phase 0: INIT

1. Read `CLAUDE.md`
2. Read `DESIGN.md` — extract scopes and principles
3. If no `DESIGN.md` exists → refuse ("Nothing to reflect against")

### Phase 1: READ

**Swarm trigger**: 2+ scopes in `DESIGN.md`

- Spawn `reader-{scope}` agents in parallel
- Each agent: scan its scope for current implementation state
- Additionally: spawn `reader-design` to self-inspect `DESIGN.md` for internal consistency
- Single scope: run inline without spawning

Collect read results into a unified context.

### Phase 2: COMPARE

Lead integrates results and performs cross-scope analysis:

1. Compare each scope's implementation against `DESIGN.md` principles
2. Classify divergences:
   - **Code drifted** — implementation violates principle
   - **Philosophy outdated** — code shows better approach
   - **New pattern** — code introduced something `DESIGN.md` doesn't cover

Run Detection Target scan (parallel):

| ID | Name | Trigger |
|----|------|---------|
| D1 | Drift | Implementation contradicts a stated principle |
| D2 | New Pattern | Code exhibits a pattern not captured in `DESIGN.md` |
| D3 | Outdated Principle | Principle references removed/changed behavior |
| D4 | Stale Reference | `DESIGN.md` links or paths no longer exist |
| D5 | Self-Contradiction | Two principles in `DESIGN.md` conflict with each other |

### Phase 3: REPORT

**STOP gate** — Present divergence report to user. Do NOT modify `DESIGN.md` without approval.

Report format:
```
| # | Type | Principle | Finding | Recommendation |
|---|------|-----------|---------|----------------|
```

Wait for user to approve, reject, or modify each recommendation.

### Phase 4: APPLY

**Swarm trigger**: 2+ approved changes across scopes

- Spawn `writer-{scope}` agents in parallel batches
- Apply only approved changes
- Single scope: apply inline

After applying:
1. Summarize what changed
2. Suggest next command if applicable

## Constraints

- Never modify `DESIGN.md` without STOP gate approval
- Can reflect on `DESIGN.md` itself (meta-reflection)
- Scopes come from `DESIGN.md`, not hardcoded paths
