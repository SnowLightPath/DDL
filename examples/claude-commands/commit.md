# commit

Record verified code changes to the repository.

## Usage

- `/commit` — Commit locally only
- `/commit remote` — Commit and push

## Phases

### Phase 0: INIT

1. Read `.claude/commands/DDL-PROTOCOL-SKILL.md`
2. Read `CLAUDE.md`
3. Read `design.md` — extract scopes, validation commands
4. Run `git status` and `git diff --staged` to understand current state

### Phase 1: VERIFY

Run validation checks in parallel:

1. Run all validation commands defined in `design.md` (if any)
2. Secret scan: check staged files for API keys, tokens, credentials
3. Check for untracked files that should be included

+++DETECT:
  D1: Failing Check — A validation command from design.md fails
  D2: Secret Leak — Staged file contains API key, token, or credential
  D3: Unrelated Change — Staged files span unrelated scopes without justification
  D4: Missing File — A new file is referenced but not staged
  D5: AI Attribution — Commit message or code contains AI co-author tags

+++STOP: on D1
+++STOP: on D2

### Phase 2: REVIEW

+++STOP: always

+++Report:
Files: <list of staged files>
Scope: <affected scopes from design.md>
Message: <proposed commit message>
Detection: <any targets that fired>

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
+++NEVER: Hardcode validation commands — they come from design.md
