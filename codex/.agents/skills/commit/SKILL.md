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

A command run from a user-level install follows the project's own copy when one exists (`.claude/skills/<name>/SKILL.md` in Claude Code, `.agents/skills/<name>/SKILL.md` in Codex, or the file the project's instruction file names as the command's source): the project's version is the one that runs.

1. Read the DDL protocol when it is not already in context: the project's copy when present (`.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `.agents/skills/ddl-protocol/SKILL.md` in Codex, or the file the project's instruction file names as the protocol); otherwise the user-level copy (`$HOME/.claude/skills/ddl-protocol/SKILL.md` in Claude Code, `$HOME/.codex/skills/ddl-protocol/SKILL.md` in Codex).
2. Read project-local runtime guidance when it is not already in context (the runtime loads `AGENTS.md` for Codex, and `CLAUDE.md` or `.claude/CLAUDE.md` for Claude Code, at session start), and any applicable command overlay.
3. Read `design.md` when it is not already in context — extract scopes, validation commands
4. If no `design.md` exists → skip the design.md checks and say so in the report
5. Run `git status` and `git diff --staged` to understand current state

### Phase 1: VERIFY

Run validation checks in parallel:

1. Run all validation commands defined in `design.md` (if any)
2. Secret scan: check the files the commit would include (staged, unstaged, and the untracked files proposed for `Files`) for API keys, tokens, credentials
3. Check for untracked files that should be included

+++DETECT:
  D1: Failing Check — A validation command from design.md exits non-zero, cannot run, or prints other than the expected value declared with it
  D2: Secret Leak — A file the commit would include contains an API key, token, or credential
  D3: Unrelated Change — The files the commit would include span unrelated scopes without justification
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
| Scope | {affected design.md scopes} |
| Message | {commit message} |
| Detection | {any targets that fired} |
| Push | {no, or the remote and branch} |

Wait for user approval before proceeding.

### Phase 3: COMMIT

**Pre-condition.** Enter this phase only after explicit user approval at the Phase 2 STOP gate (per §1.5 of the protocol). If the most recent user message is not an approval token, return to Phase 2 and re-emit the report.

1. Stage approved files
2. Verify that `git diff --staged --name-only` matches the approved `Files` set exactly. If it does not, do not commit; return to Phase 2 with the mismatch.
3. Re-run the secret scan against the exact staged content. If D2 fires, do not commit or edit; STOP below, and after approval correct the staged content and restart Phase 3.

+++STOP: on D2

4. Create commit with approved message
5. Report commit hash

### Phase 4: PUSH (optional)

Only if user specified `remote` or explicitly requested:

1. Push to remote
2. Report push result

## Constraints

+++NEVER: Add AI attribution to commit messages
+++NEVER: Skip +++STOP even for small changes
+++NEVER: Hardcode validation commands — they come from design.md
+++NEVER: Sync changes between repositories or machines by copying files; use the remote (branches, pushes, pulls, pull requests)
