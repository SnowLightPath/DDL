# Claude Code: Git review

## Read when

Read before the shared [Git review](../git-review.md) for every ordinary commit or push; it names the helper path, `AskUserQuestion` for `nativeRequest` and the push rule in `.claude/settings.json`.

## Mapping

| Concern | Procedure |
|---|---|
| Prepare | `python3 "$HOME/.claude/hooks/ddl_gate.py" prepare-git-review --runtime claude` with the request JSON (Formats) on stdin; the project copy is `"$CLAUDE_PROJECT_DIR"/.claude/hooks/ddl_gate.py`, the development source `tools/ddl_gate.py`. |
| `nativeRequest` | Pass it unchanged as the `AskUserQuestion` arguments (title, labels, descriptions, selection mode) and wait for the submitted answer; a result carrying `afkTimeoutMs` is no submission. |
| Revocation | The `UserPromptSubmit` hook event is the boundary that revokes earlier preparations. |
| Push confirmation | `permissions.ask` rule `Bash(git push *)` in `.claude/settings.json` asks for native permission in every permission mode, in addition to the content review; a native grant without a matched review is denied. |
| Attribution | `attribution` in `.claude/settings.json` is empty (`commit` and `pr` empty, `sessionUrl: false`). |

## Observed

| Fact | Version | Date |
|---|---|---|
| Idle auto-resolution of `AskUserQuestion` carried `afkTimeoutMs` even when selected answers were returned; the gate does not count such a result as the human submission a Git review needs | Claude Code 2.1.316 | 2026-11-01 |

## Coverage

- The hook denies a recognized unreviewed `git commit` or `git push` only when the call reaches PreToolUse; the review handler fits the hook's `timeout: 10` (0.04 s per call in the live run, Observed in [approval](claude-approval.md)).
- A native `permissions.ask` grant proves nothing about content, and a suppressed native prompt does not suppress the hook: the matched review is required either way.
