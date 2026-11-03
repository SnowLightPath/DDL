# Claude: Git review

## Read when

Read before the shared Git review operation for every ordinary commit or push; it names the helper path, `AskUserQuestion` for `nativeRequest` and the hook's push confirmation.

## Mapping

| Concern | Implementation |
|---|---|
| Prepare | `python3 "$HOME/.claude/hooks/ddl_gate.py" prepare-git-review --runtime claude` with the request JSON (Formats) on stdin; the project copy is `"$CLAUDE_PROJECT_DIR"/.claude/hooks/ddl_gate.py`, the development source `tools/ddl_gate.py`. |
| `nativeRequest` | Pass it unchanged as the `AskUserQuestion` arguments (title, labels, descriptions, selection mode) and wait for the submitted answer; a result carrying `afkTimeoutMs` is no submission. |
| Revocation | A typed message is a `UserPromptSubmit` and revokes; an `AskUserQuestion` answer is not one and keeps the preparation. |
| Push confirmation | After the matched content review the hook answers an ordinary `git push` with `permissionDecision: ask`, only in a DDL project, so the push is still confirmed natively; no `permissions.ask` rule is installed; a native grant without a matched review is denied; behavior under `bypassPermissions` / `dontAsk` is unverified. |
| Attribution | `attribution` in `.claude/settings.json` is empty (`commit` and `pr` empty, `sessionUrl: false`). |

## Observed

| Fact | Version | Date |
|---|---|---|
| Idle auto-resolution of `AskUserQuestion` carried `afkTimeoutMs` even when selected answers were returned; the gate does not count such a result as the human submission a Git review needs | Claude Code 2.1.316 | 2026-11-01 |

## Coverage

- The hook denies a recognized unreviewed `git commit` or `git push` only when the call reaches PreToolUse; the review handler fits the hook's `timeout: 10` (0.04 s per call in the live run, Observed in approval).
- The hook's `ask` adds no content proof, and a suppressed native prompt does not suppress the hook: the matched review is required either way; the hook reads no `permission_mode` here, so its content denial holds under `bypassPermissions`, `dontAsk` and `acceptEdits` alike.
