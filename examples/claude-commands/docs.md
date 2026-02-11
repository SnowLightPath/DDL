# docs

Audit and fix documentation quality.

## Usage

- `/docs` — Audit all documentation
- `/docs <path>` — Audit specific document or directory

## Phases

### Phase 0: INIT

1. Read `CLAUDE.md`
2. Read `DESIGN.md` — extract scopes and documentation paths
3. Discover all documentation files

### Phase 1: DISCOVER

**Swarm trigger**: 2+ scopes in `DESIGN.md`

- Spawn `scanner-docs` agent: inventory all documentation files, extract structure
- Spawn `scanner-{scope}` agents in parallel: scan source code for public APIs, exports, types
- Single scope: run inline without spawning

Collect discovery results into a unified context.

### Phase 2: AUDIT

Lead integrates results and checks:

1. Cross-reference documentation against source code
2. Verify code examples conceptually
3. Check internal links and references

Run Detection Target scan (parallel):

| ID | Name | Trigger |
|----|------|---------|
| D1 | Stale Version | Doc references outdated version, API, or behavior |
| D2 | Broken Reference | Internal link or file path no longer exists |
| D3 | Missing Section | Public API or feature has no documentation |
| D4 | Stale Example | Code example doesn't match current implementation |
| D5 | Structure Mismatch | Doc structure doesn't match `DESIGN.md` conventions |
| D6 | Wrong Names | Doc uses names that don't exist in codebase |

### Phase 3: REPORT

**STOP gate** — Present audit report to user. Do NOT fix without approval.

Report format:
```
| # | File | Type | Finding | Fix |
|---|------|------|---------|-----|
```

Wait for user to approve, reject, or modify each fix.

### Phase 4: FIX

**Swarm trigger**: 2+ approved fixes across different files

- Spawn `writer-{scope}` agents in parallel batches
- Each agent: apply approved fixes to its documentation files
- Single scope: fix inline

### Phase 5: VERIFY

Re-scan fixed files to confirm:

1. No new Detection Targets introduced
2. All approved fixes applied correctly
3. Summarize final state

## Constraints

- Never modify documentation without STOP gate approval
- Scopes and paths come from `DESIGN.md`, not hardcoded
