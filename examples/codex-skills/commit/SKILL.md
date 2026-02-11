---
name: commit
description: Record verified code changes to the repository
metadata:
  short-description: Verified git commit
---

# commit

Record verified code changes to the repository.

## Usage

- `$commit` — Commit locally only
- `$commit remote` — Commit and push

## Phases

### Phase 0: INIT

1. Read `AGENTS.md`
2. Run `git status` and `git diff --staged` to understand current state

### Phase 1: VERIFY

Run validation checks:

1. Run all validation commands defined in `DESIGN.md` (if any)
2. Secret scan: check staged files for API keys, tokens, credentials
3. Check for untracked files that should be included

Run Detection Target scan:

| ID | Name | Trigger |
|----|------|---------|
| D1 | Failing Check | A validation command from `DESIGN.md` fails |
| D2 | Secret Leak | Staged file contains API key, token, or credential |
| D3 | Unrelated Change | Staged files span unrelated scopes without justification |
| D4 | Missing File | A new file is referenced but not staged |
| D5 | AI Attribution | Commit message or code contains AI co-author tags |

**STOP on D1/D2**: If Failing Check or Secret Leak detected → halt immediately.

### Phase 2: REVIEW

**STOP gate** — Present commit summary to user for approval.

### Phase 3: COMMIT

1. Stage approved files
2. Create commit with approved message
3. Report commit hash

### Phase 4: PUSH (optional)

Only if user specified `remote` or explicitly requested.

## Constraints

- NEVER add AI attribution to commit messages
- NEVER skip STOP gate even for small changes
- Validation commands come from `DESIGN.md`, not hardcoded
