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
3. Discover all documentation files

### Phase 1: DISCOVER

Inventory all documentation files. Then, for each scope in `DESIGN.md`, sequentially scan source code for public APIs.

### Phase 2: AUDIT

Cross-reference documentation against source code. Check:

1. Code examples match implementation
2. Internal links resolve
3. All public APIs are documented

Run Detection Target scan:

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

### Phase 4: FIX

Apply approved fixes to documentation files.

### Phase 5: VERIFY

Re-scan fixed files to confirm no new issues introduced.

## Constraints

- Never modify documentation without STOP gate approval
- Scopes and paths come from `DESIGN.md`, not hardcoded
