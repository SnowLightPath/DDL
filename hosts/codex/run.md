# Codex: run

## Read when

Read before a plan names a grant, a snapshot is made or a resource is used, with the Run operation; it names the grant store, the hooks' decision under a grant, the event file, the unmeasured answer times, the subcommands and how resources are reached.

## Mapping

| Concern | Implementation |
|---|---|
| Grant record | Written by the gate at the first PreToolUse call that follows the human's reply (step 1), else at Stop; the user-level store is `$DDL_GATE_GRANT_DIR`, else `$XDG_STATE_HOME/ddl-gate`, else `$HOME/.local/state/ddl-gate`. |
| Decision | PreToolUse denies a call step 1 denies and returns nothing for one it allows, which the PermissionRequest hook then allows (Git review's Decision row); none for a call run by a shell other than bash, sh, zsh or dash, and only a read's from a `workdir` outside the root. |
| Event record | The hook's events append to `.ddl/events.jsonl`. |
| Answer time | From the ledger (a Run or a session): the hook's clock at the question's PreToolUse call and at the reply's UserPromptSubmit. From a rollout: the `timestamp` of the question call's line and of the reply message's line, both unmeasured; a line without one gives `not measured`. |
| Subcommands | `python3 "$HOME/.codex/hooks/ddl_gate.py" report --run <N-id>` (or `--session <id>`, or `--runtime codex --transcript <file>`); `run-start` (JSON on stdin), `run-item <N-id> <item> <status>`, `snapshot [--run <N-id>] [--item <id>] [--git-dir <dir> --work-tree <dir>]` (or `snapshot list`), `resources`, `measure <machine>`, `remote <machine> [--snapshot <ref|commit>] [--run <N-id>] [--item <id>] [--artifacts <glob>…] [--timeout <minutes>] [--keep] [--confirmed <R-id>] -- <command>…` and `service <name> --prompt-file <file> [--schema <file>] [--approve] [--confirmed <R-id>]` likewise, or the project copy, from inside the project; unavailable while a decision is pending. |
| Resources | A `codex:` service carrying `confirm`, and any write to a service, only through `service`; a read may use the plugin itself; `remote` for an ssh machine. |

## Observed

| Fact | Version | Date |
|---|---|---|
| Under `codex exec -s workspace-write` in a scratch repository a shell command could not create a file under `.git/` and could create one under a hidden directory of the work tree; the user-level hooks ran for PreToolUse and Stop | codex-cli 0.167.2 | 2026-11-23 |

## Coverage

- The gate does not see a plugin call made directly: the Resources row binds as an instruction only.
- No grant is recorded where `transcript_path` is null (its proof reads the rollout) or before the hooks are trusted and enabled.
- Unverified: whether a hook process can write the user-level store (if not, that grant is never recorded); whether a hook runs for a subagent's tool call with an identifier; a live grant record and allow (simulated dispatch only).
