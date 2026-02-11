# resonate

Synchronize multilingual document versions.

## Arguments

$ARGUMENTS: Target file or directory

## Phases

### Phase 0: INIT

1. Read `CLAUDE.md`
2. Read `DESIGN.md` — identify multilingual document pairs
3. Discover language counterparts in target path

### Phase 1: READ

**Swarm trigger**: 2+ document pairs

- Spawn `reader-{lang}` agents in parallel
- Each agent: parse its language version, extract section structure and content
- Single pair: read inline without spawning

Collect parsed structures into a unified context.

### Phase 2: COMPARE

Section-by-section comparison across language pairs:

1. Align sections by heading structure
2. Identify dissonance per section

Run Detection Target scan (parallel):

| ID | Name | Trigger |
|----|------|---------|
| D1 | Missing Nuance | Translation loses meaning present in source |
| D2 | Different Emphasis | Section weight or tone differs between languages |
| D3 | Structural Mismatch | Heading hierarchy or section order differs |
| D4 | Untranslated Section | Section exists in one language but not the other |
| D5 | Stale Translation | Source updated after translation was last changed |

### Phase 3: REPORT

**STOP gate** — Present dissonance table to user. Do NOT apply changes without approval.

Report format:
```
| # | Section | Type | Lang A | Lang B | Proposal |
|---|---------|------|--------|--------|----------|
```

Wait for user to approve, reject, or modify each proposal.

### Phase 4: APPLY

Apply approved changes to BOTH language versions.

**Swarm trigger**: 2+ document pairs with approved changes

- Spawn `writer-{lang}` agents in parallel
- Each agent: apply changes to its language version
- Single pair: apply inline

## Example

```
Human: /resonate docs/

Claude: Comparing Lang A and Lang B...

| # | Section | Type | Lang A | Lang B | Proposal |
|---|---------|------|--------|--------|----------|
| 1 | Intent | D1 Missing Nuance | "share design" | (loses "across sessions") | Lang A → "share design across sessions" |

Apply approved changes?
```

## Constraints

- Proposals refine BOTH versions — neither language is strictly "source"
- Never auto-apply — STOP gate is mandatory
