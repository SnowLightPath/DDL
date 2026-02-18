---
name: docs
description: Audit and fix documentation quality
metadata:
  short-description: Documentation audit
---

# docs

Audit and fix documentation quality.

## Usage

- `$docs` — Audit all documentation
- `$docs <path>` — Audit specific document or directory

## Phases

### Phase 0: INIT

1. Read `AGENTS.md`
2. Read `DESIGN.md` — extract scopes and documentation paths
3. Discover all documentation files (`.md`, `.txt`, etc.)

### Phase 1: DISCOVER

+++SWARM: 2+ scopes in DESIGN.md

```
  team: docs-discover
  spawn: scanner-{scope}
  type: Explore
  max: 5
  batch: auto
  each: |
    Inventory documentation files and scan source for public APIs, exports, types in {scope}.
  collect: lead collects discovery results into a unified context
```

### Phase 2: AUDIT

Lead integrates results and checks:

1. Cross-reference documentation against source code
2. Verify code examples compile/run conceptually
3. Check internal links and references

+++DETECT:
  D1: Stale Version — Doc references outdated version, API, or behavior
  D2: Broken Reference — Internal link or file path no longer exists
  D3: Missing Section — Public API or feature has no documentation
  D4: Stale Example — Code example doesn't match current implementation
  D5: Structure Mismatch — Doc structure doesn't match DESIGN.md conventions
  D6: Wrong Names — Doc uses names that don't exist in codebase

### Phase 3: REPORT

+++STOP: always

Do NOT fix without approval.

+++Report:
| # | File:Line | Type | Finding | Suggested Fix |
|---|-----------|------|---------|---------------|

Wait for user to approve, reject, or modify each fix.

### Phase 4: FIX

+++SWARM: 2+ approved fixes across different files

```
  team: docs-fix
  spawn: writer-{scope}
  type: general-purpose
  max: 5
  batch: auto
  each: |
    Apply approved fixes to {scope} documentation.
  collect: lead verifies all fixes applied correctly
```

### Phase 5: VERIFY

Re-scan fixed files to confirm:

1. No new Detection Targets introduced
2. All approved fixes applied correctly
3. Summarize final state

## Constraints

+++NEVER: Modify documentation without +++STOP approval
+++NEVER: Hardcode scopes or paths — they come from DESIGN.md
+++NEVER: Execute code examples — check conceptually only
