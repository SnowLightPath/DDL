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

After those checks pass, prepare the final candidate set for review:

4. Stage only the proposed files. Preserve unrelated existing staged changes: include them in the complete review when justified, or leave them intact and resolve the scope before proceeding. Staging is reversible review preparation; it does not authorize a commit. State the staged set in the review detail.
5. Use the runtime adapter's Git-review preparation procedure (protocol §2.5) to freeze the staged contents, exact message, and any explicitly requested push. The ordinary message form preserves the reviewed text verbatim. Group all compatible ready operations into one review; put a repository's planned commit before its push. A plan approved before the final diff existed supplies no Git approval (§1.6).
6. If there are no commit candidates and no requested push, issue an informational report; do not invent an approval or empty commit.

+++DETECT:
  D1: Failing Check — A validation command from design.md exits non-zero, cannot run, or prints other than the expected value declared with it
  D2: Secret Leak — A file the commit would include contains an API key, token, or credential
  D3: Unrelated Change — The files the commit would include span unrelated scopes without justification
  D4: Missing File — A new file is referenced but not staged
  D5: AI Attribution — Commit message or code contains AI co-author tags
  D6: Git Review Mismatch — The prepared review, native submitted answer, staged contents, message, or destination cannot be matched

+++STOP: on D1
+++STOP: on D2

### Phase 2: REVIEW

+++STOP: always

+++Report:
Decision: create the proposed commit, revise it, or leave it uncommitted.
Recommendation: the commit's purpose and why the proposed files belong together; keep material detections visible.
Consequence: commit exactly `Files` with the exact `Message`; state whether `Push` is no or names the remote and branch, and include any requested push in the selected action explicitly.
Review detail: the complete `Files` list and diff, affected `Scope`, exact `Message`, every material `Detection`, and `Push`. Show the prepared review ID and link its complete report before asking; all must be accessible before approval.
Choices: use the prepared native question and its exact action labels for one whole-set approval (§1.6, runtime mapping in §2.5). Do not replace it with an arbitrary question or ask again per file. Approval of a different file set, message, or push target is not approval of this proposal.

### Phase 3: COMMIT

**Pre-condition.** Enter this phase only after explicit user approval of its scope at the Phase 2 STOP gate (per §1.5 of the protocol). If the actual answer does not authorize this work, return to Phase 2 and re-present the current decision.

1. Keep the reviewed index intact. Do not restage newer working-tree contents after approval.
2. Verify that the staged file set, contents, base, and message still match the prepared review. If they differ, do not commit; rebuild the review and return to Phase 2. The hook independently checks supported calls, including when no STOP is pending (§1.6).
3. Re-run the secret scan against the exact staged content. If D2 fires, do not commit or edit; STOP below, and after approval correct the staged content and restart Phase 3.

+++STOP: on D2
+++STOP: on D6

4. Create the reviewed commit with the approved verbatim message using the supported ordinary form (§2.5)
5. Report the commit hash as progress. Do not emit a new STOP report between an approved commit and its approved push; finish the reviewed set before the final informational report

### Phase 4: PUSH (optional)

Only if user specified `remote` or explicitly requested:

1. Verify the reviewed source commit, resolved remote, and destination branch; push only the reviewed operation. A changed or unapproved target returns to Phase 2. A single approval covers the ready commit and its stated push; do not ask again merely because the commit has now been created
2. Report push result

## Constraints

+++NEVER: Add AI attribution to commit messages
+++NEVER: Skip +++STOP even for small changes
+++NEVER: Treat a normal reply or an assistant-authored approval claim as a Git review receipt; alter frozen review detail; or bypass the guard with another transport
+++NEVER: Hardcode validation commands — they come from design.md
+++NEVER: Sync changes between repositories or machines by copying files; use the remote (branches, pushes, pulls, pull requests)
