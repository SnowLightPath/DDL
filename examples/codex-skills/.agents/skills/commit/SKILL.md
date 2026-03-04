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
- `$commit --sync-port` — Commit, then sync scribe-plugin to snow-light-place

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

### Phase 5: SYNC-PORT (optional)

Only if user specified `--sync-port`:

1. Check if `examples/scribe-plugin/` has changes in the current commit
2. If no scribe changes → report "No scribe changes to sync" and skip
3. Sync `examples/scribe-plugin/` → `../snow-light-place/scribe/` (overwrite plugin files only, preserve marketplace metadata)
4. In snow-light-place repo: stage, commit with same message, push to remote
5. Run V21 from `DESIGN.md` to verify sync

+++DETECT:
  D6: Port Divergence — snow-light-place/scribe differs from examples/scribe-plugin after sync
  D7: Identity Mismatch — snow-light-place commit author is not SnowLightPath

+++STOP: on D6
+++STOP: on D7

## Constraints

+++NEVER: Add AI attribution to commit messages
+++NEVER: Skip +++STOP even for small changes
+++NEVER: Hardcode validation commands — they come from DESIGN.md
