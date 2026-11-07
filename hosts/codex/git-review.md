# Codex: Git review

## Read when

Read for every ordinary commit or push, before the shared Git review operation; it names the helper path, `request_user_input_async` for `nativeRequest` and the push rule in `.codex/rules/ddl.rules`.

## Mapping

| Concern | Implementation |
|---|---|
| Prepare | Approval's Prepare row with `prepare-git-review --runtime codex` and the request JSON (Formats) on stdin. |
| `nativeRequest` | Unchanged as the `request_user_input_async` arguments (`title` with the five lines, option labels; no descriptions or selection mode); end the turn after the receipt and wait for the `UserMessage` reply, which the hook matches by call ID, question and selected action; an unreadable or unsupported reply denies even under `never`, `bypassPermissions` or `dontAsk`. |
| Revocation | `UserPromptSubmit` revokes; a possible matching native submission is preserved pending full request/result proof. |
| Push confirmation | `.codex/rules/ddl.rules` (project trust): `prefix_rule` on `["git", "push"]`, `decision = "prompt"`, so a supported literal `git push ...` reaches the native prompt when the approval policy allows prompting; the hook's static form guard, independent of STOP, rejects recognized push forms that miss that prefix (Git global options, wrappers) with a canonical retry, never rewriting or allowing, and absolute host Git paths keep native resolution; `bypassPermissions` / `dontAsk` hook modes skip only this guard, a never-prompting session shows nothing, and the `$commit` report's approval still applies. |
| Attribution | Codex adds no attribution of its own. |

## Observed

| Fact | Version | Date |
|---|---|---|
| The installed binary maps approval policy `never` to hook mode `bypassPermissions` and other policies to `default` (binary inspection, no live payload); `dontAsk` is the documented explicit no-confirmation mode | Codex 0.163.0 | 2026-11-01 |
| With policy `never`, one native answer allowed the exact prepared commit and push to a disposable repository/local bare remote; hooks stayed enabled, with no manual `!` or extra push-confirmation UI | Codex Desktop 0.167.0-alpha.3.2 | 2026-11-07 |
| Offline replay of only actual question/answer items proved `native_git_choice` without assistant text | Codex Desktop 0.167.0-alpha.3.2 | 2026-11-07 |

## Coverage

- The hook denies a recognized unreviewed commit or push only when the call reaches the Codex tool hooks: the project rules and hooks under project trust, or the user-level hooks.
- `bin/doctor.sh` covers null records and the no-confirmation modes by simulated dispatch.
- The live `never` run does not test native push prompts under policies that permit prompting.
