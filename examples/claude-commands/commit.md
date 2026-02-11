# commit

Record verified code changes to the repository.

## Usage

- `/commit` — Commit locally only
- `/commit remote` — Commit and push

## Phases

### Phase 0: INIT

1. Read `CLAUDE.md`
2. Run `git status` and `git diff --staged` to understand current state

### Phase 1: VERIFY

Run validation checks in parallel:

1. Run all validation commands defined in `DESIGN.md` (if any)
2. Secret scan: check staged files for API keys, tokens, credentials
3. Check for untracked files that should be included

Run Detection Target scan (parallel):

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

Summary format:
```
Files: <list of staged files>
Scope: <affected scopes from DESIGN.md>
Message: <proposed commit message>
Detection: <any targets that fired>
```

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

- NEVER add AI attribution to commit messages
- NEVER skip STOP gate even for small changes
- Validation commands come from `DESIGN.md`, not hardcoded
