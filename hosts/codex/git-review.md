# Codex: Git review

## Read when

Read for every ordinary commit or push, before the shared Git review operation; it names the helper path, `request_user_input_async` for `nativeRequest` and the hooks' decision.

## Mapping

| Concern | Implementation |
|---|---|
| Prepare | Approval's Prepare row with `prepare-git-review --runtime codex` and the request JSON (Formats) on stdin. |
| `nativeRequest` | Unchanged as the `request_user_input_async` arguments (`title` with the five lines, option labels; no descriptions or selection mode); end the turn after the receipt and wait for the `UserMessage` reply, which the hook matches by call ID, question and selected action; an unreadable or unsupported reply denies even under `never`, `bypassPermissions` or `dontAsk`. |
| Revocation | `UserPromptSubmit` revokes; a possible matching native submission is preserved pending full request/result proof. |
| Decision | PreToolUse never allows (Observed): it denies an unmatched commit or push and returns nothing for a matched one or a commit inside a grant; when Codex then asks for permission, the PermissionRequest hook (`permission-request`) answers `decision.behavior: allow` (none for an escalated call) and nothing else. The static form guard, independent of STOP, denies recognized push forms the review cannot read (Git global options, wrappers) with a canonical retry, never rewriting; absolute host Git paths keep native resolution; `bypassPermissions` / `dontAsk` hook modes skip only this guard. |
| Attribution | Codex adds no attribution of its own. |

## Observed

| Fact | Version | Date |
|---|---|---|
| The installed binary maps approval policy `never` to hook mode `bypassPermissions` and other policies to `default` (binary inspection, no live payload); `dontAsk` is the documented explicit no-confirmation mode | Codex 0.163.0 | 2026-11-01 |
| With policy `never`, one native answer allowed the exact prepared commit and push to a disposable repository/local bare remote; hooks stayed enabled, with no manual `!` or extra push-confirmation UI | Codex Desktop 0.167.0-alpha.3.2 | 2026-11-07 |
| Offline replay of only actual question/answer items proved `native_git_choice` without assistant text | Codex Desktop 0.167.0-alpha.3.2 | 2026-11-07 |
| `PostToolUse` is a hook event of the binary and of the hooks documentation (shell and unified exec match as `Bash`; a new hook is skipped until trusted in `/hooks`); no live run | codex-cli 0.171.0 | 2026-11-24 |
| Binary inspection, no live run: PreToolUse refuses `permissionDecision` `allow` and `ask` as unsupported; a PermissionRequest output takes `decision.behavior` `allow` or `deny` and fails closed on `updatedInput`, `updatedPermissions` or `interrupt: true` | codex-cli 0.171.0 | 2026-11-24 |

## Coverage

- The hook acts only on a call that reaches the Codex tool hooks: the project hooks under project trust, or the user-level hooks.
- `bin/doctor.sh` covers null records and the no-confirmation modes by simulated dispatch.
- The PermissionRequest allow is unchecked live, and so is whether a user's `prompt` or `forbidden` rule still applies after it; a call Codex runs without asking never reaches that hook.
