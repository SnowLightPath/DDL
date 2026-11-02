# Codex: Git review

## Read when

Read this before the shared [Git review](../git-review.md) procedure, for every ordinary `git commit` or `git push` (the Close step and `$commit`). It names the helper path, the choice tool and the native push rule in Codex.

## Mapping

| Concern | Procedure |
|---|---|
| Prepare | Run `python3 "$HOME/.codex/hooks/ddl_gate.py" prepare-git-review --runtime codex` with the JSON (`language`, `operations[]` with `cwd` and `command`) on stdin; project copy `.codex/hooks/ddl_gate.py` at the repository root, development source `tools/ddl_gate.py` in this repository. The helper snapshots the staged set and returns `reviewId` (`G-<id>`), `report` (the path of `report.md`), `question` and `nativeRequest`. Show the ID and link the report before asking. Use the shell tool's working directory for the intended repository. |
| `nativeRequest` | Pass `nativeRequest` unchanged as the arguments of the permitted `request_user_input_async`, keeping its exact title, labels, descriptions and selection mode; end the turn after the receipt and wait for the actual reply. The hook matches the actual call ID to the submitted `UserMessage` reply, the question and the selected action; an unreadable, unsupported or unprovable reply denies the operation, even under `never`, `bypassPermissions` or `dontAsk`. A fabricated receipt or typed approval cannot replace the native answer. |
| Revocation | An ordinary `UserPromptSubmit` revokes older preparations at once, even before the transcript flushes; a possible matching native submission is preserved pending full request/result proof. Resume or compaction invalidates preparations through the session epoch (`<session>.git-epoch`). Prepare again after such a boundary and after any change to the staged set, message or branch. |
| Push confirmation | `.codex/rules/ddl.rules` (loaded under project trust): `prefix_rule` on `["git", "push"]` with `decision = "prompt"`, so a supported literal `git push ...` reaches the native prompt when the session's approval policy permits prompting. Independently of STOP, the hook's static form guard rejects recognized push forms that miss that prefix (Git global options, explicit wrappers) with a canonical retry and no rewriting or affirmative allow; retry in the intended working directory only when the options keep the same meaning, otherwise explain the limitation. Absolute host Git paths keep native executable resolution. Explicit `bypassPermissions` / `dontAsk` hook modes skip only this form guard; STOP and the content review still apply. A never-prompting session shows nothing, and the approval in the `$commit` report still applies. |
| Attribution | Codex adds no attribution; never add AI attribution in the message by hand. |

## Observed

| Fact | Version | Date |
|---|---|---|
| The installed binary maps approval policy `never` to hook mode `bypassPermissions` and other policies to `default` (binary inspection, not a captured live payload); `dontAsk` is accepted as the documented explicit no-confirmation mode | Codex 0.163.0 | 2026-11-01 |
| The Default-mode CLI cleared the async selector at turn completion, so a Git review question through `request_user_input_async` could not be answered on that route; the GUI host of the same chat retained click replies | Codex CLI 0.166.0 | 2026-11-01 |

## Coverage

- The hook denies recognized ordinary `git commit` and `git push` calls that reach the tool hooks without a prepared review matched to the actual native submission and the current Git snapshot (repository, base, staged contents, message, branch; for a push the source commit, resolved remote and destination), even while a STOP is open or native prompts are suppressed. Git read commands keep working.
- The check covers recognized calls dispatched through the hook, not arbitrary programs, aliases, state-changing Git hooks, concurrent index changes or input to an existing process; it never grants, rewrites or stages. Review files under `<state dir>/git-reviews/<id>/` (`report.md`, `review.json`, patches) carry no approval flag; the submission must be proved from the conversation record.
- An unprovable recognized review fails closed inside a running handler, while a runtime-level hook failure or timeout can still fail open; verification uses a shorter internal time budget than the hook's `timeout: 10`. Project-local rules and hooks need project trust.
- Installation diagnostics check unapproved commit/push rejection through both adapters, including OPEN/null records and no-confirmation modes, and deterministic tests execute the configured hook commands in both installation layouts; simulated dispatch proves neither native hook trust nor the interactive approval UI.
