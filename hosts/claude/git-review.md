# Claude: Git review

## Read when

Read before the shared Git review operation for every ordinary commit or push; it names the helper path, `AskUserQuestion` for `nativeRequest` and the hook's decision.

## Mapping

| Concern | Implementation |
|---|---|
| Prepare | `prepare-git-review --runtime claude` on the gate of approval's Prepare row, the request JSON (Formats) on stdin. |
| `nativeRequest` | Pass it unchanged as the `AskUserQuestion` arguments (the five lines, header `Git`, labels, descriptions, selection mode) and wait for the submitted answer; a result carrying `afkTimeoutMs` is no submission. |
| Revocation | A typed message is a `UserPromptSubmit` and revokes; an `AskUserQuestion` answer is not one and keeps the preparation. |
| Decision | PreToolUse answers a commit or push that matches the answered review with `permissionDecision: allow`, reason `DDL: matches Git review <G-id>` (a commit inside a grant: `DDL: inside grant <R-id> (commit)`; none with `dangerouslyDisableSandbox`), and an unmatched one with `deny`. |
| Attribution | `attribution` in `.claude/settings.json` is empty (`commit` and `pr` empty, `sessionUrl: false`). |

## Observed

| Fact | Version | Date |
|---|---|---|
| Idle auto-resolution of `AskUserQuestion` carried `afkTimeoutMs` even when selected answers were returned; the gate does not count such a result as the human submission a Git review needs | Claude Code 2.1.316 | 2026-11-01 |
| In that session (Harness 5d585b21), with the reports recorded only as thinking (approval, Observed), the gate found no `+++DDL_REPORT` naming the review and denied three approved pushes (G-30d7aa1a2557fc22, G-53c241508ddaf721, G-ac1c480ef1e3382d) | Claude Code 2.1.317 in the record, 2.1.319 binary | 2026-11-07 |

## Coverage

- The hook acts only on a call that reaches PreToolUse; the review handler fits the hook's `timeout: 10` (0.04 s per call in the live run, Observed in approval).
- A suppressed native prompt does not suppress the hook: it reads no `permission_mode` here, so its content denial holds under `bypassPermissions`, `dontAsk` and `acceptEdits` alike. A user's `deny` or `ask` rule still applies after its `allow` (the host's documented order, not observed here).
