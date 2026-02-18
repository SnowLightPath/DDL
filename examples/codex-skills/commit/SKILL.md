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
2. Read `DESIGN.md` — extract scopes, validation commands
3. Run `git status` and `git diff --staged` to understand current state

### Phase 1: VERIFY

Run validation checks:

1. Run all validation commands defined in `DESIGN.md` (if any)
2. Secret scan: check staged files for API keys, tokens, credentials
3. Check for untracked files that should be included

+++DETECT:
  D1: Failing Check — A validation command from DESIGN.md fails
  D2: Secret Leak — Staged file contains API key, token, or credential
  D3: Unrelated Change — Staged files span unrelated scopes without justification
  D4: Missing File — A new file is referenced but not staged
  D5: AI Attribution — Commit message or code contains AI co-author tags

+++STOP: on D1
+++STOP: on D2

### Phase 2: REVIEW

+++STOP: always

+++Report:
| Field | Value |
|-------|-------|
| Files | {list of changed files} |
| Scope | {affected DESIGN.md scopes} |
| Message | {commit message} |
| Detection | {any targets that fired} |

Wait for user approval before proceeding.

### Phase 3: COMMIT

1. Stage approved files
2. Create commit with approved message
3. Report commit hash

### Phase 4: PUSH (optional)

Only if user specified `remote` or explicitly requested:

1. Push to remote
2. Report push result

## Constraints

+++NEVER: Add AI attribution to commit messages
+++NEVER: Skip +++STOP even for small changes
+++NEVER: Hardcode validation commands — they come from DESIGN.md
